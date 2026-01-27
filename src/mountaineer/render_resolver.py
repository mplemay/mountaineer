from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, Signature, isawaitable, isclass, signature
from json import loads as json_loads
from typing import Annotated, Any, Callable, Iterable, get_args, get_origin
from urllib.parse import urlparse

from fastapi import Request, params as fastapi_params
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, TypeAdapter, ValidationError
from starlette.routing import Match

from mountaineer.dependencies import (
    get_function_dependencies,
    isolate_dependency_only_function,
)
from mountaineer.exceptions import RequestValidationError, RequestValidationFailure
from mountaineer.render import Metadata, RenderBase, RenderNull


@dataclass(kw_only=True)
class RenderResolution:
    render_model: type[RenderBase]
    data: dict[str, Any]
    metadata: Metadata | None


class RenderResolver:
    @staticmethod
    async def resolve(
        *,
        controller: Any,
        request: Request | None = None,
        values: dict[str, Any] | None = None,
        loaders: Iterable[Callable] | Iterable[str] | None = None,
        metadata_loader: Callable | None = None,
    ) -> RenderBase | dict[str, Any] | Response:
        page_request = RenderResolver._get_page_request(controller, request)

        params_model = getattr(controller, "_page_params_model", None)
        params_instance = RenderResolver._build_params_instance(
            params_model=params_model,
            request=page_request,
            values=values,
        )

        data_defs: Iterable[Any] | None = getattr(controller, "_page_data_defs", None)
        if data_defs is None:
            render_values = values or {}
            server_data = controller.render(**render_values)
            if isawaitable(server_data):
                server_data = await server_data
            if server_data is None:
                return RenderNull()
            return server_data

        data_defs = list(data_defs)
        loaders_by_name = {
            data_def.name: data_def for data_def in data_defs if hasattr(data_def, "name")
        }

        if loaders is None:
            target_defs = [data_def for data_def in data_defs if data_def.ssr]
        else:
            target_defs = []
            if isinstance(loaders, Iterable):
                for loader in loaders:
                    if isinstance(loader, str):
                        if loader not in loaders_by_name:
                            raise ValueError(f"Unknown loader: {loader}")
                        target_defs.append(loaders_by_name[loader])
                    else:
                        matched = next(
                            (
                                data_def
                                for data_def in data_defs
                                if data_def.func == loader
                            ),
                            None,
                        )
                        if matched is None:
                            raise ValueError(f"Unknown loader: {loader}")
                        target_defs.append(matched)
            else:
                raise ValueError("Invalid loaders specification")

        body_values = None
        if request is not None:
            body_values = await RenderResolver._read_body_values(request)

        loader_results: dict[str, Any] = {}
        for data_def in target_defs:
            loader_result = await RenderResolver._execute_loader(
                controller=controller,
                loader=data_def.func,
                params_model=params_model,
                params_instance=params_instance,
                request=page_request,
                values=values,
                body_values=body_values,
            )
            loader_results[data_def.name] = loader_result

        if loaders is not None:
            return loader_results

        metadata_value = None
        if metadata_loader:
            metadata_value = await RenderResolver._execute_loader(
                controller=controller,
                loader=metadata_loader,
                params_model=params_model,
                params_instance=params_instance,
                request=page_request,
                values=values,
                body_values=None,
            )
            if metadata_value is not None and not isinstance(metadata_value, Metadata):
                raise ValueError(
                    f"Metadata loader must return Metadata, got {type(metadata_value)}"
                )

        render_model = getattr(controller, "_page_render_model", RenderNull)
        render_value = render_model(**loader_results, metadata=metadata_value)
        return render_value

    @staticmethod
    def build_signature(
        loaders: Iterable[Callable],
        metadata_loader: Callable | None,
    ) -> Signature:
        parameters: list[Parameter] = []
        seen: dict[str, Parameter] = {}

        def add_param(param: Parameter):
            if param.name == "params":
                return
            if param.kind in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}:
                return
            if param.name in seen:
                existing = seen[param.name]
                if (
                    existing.annotation != param.annotation
                    or existing.default != param.default
                ):
                    raise TypeError(
                        f"Duplicate parameter {param.name} with conflicting definitions"
                    )
                return
            param = param.replace(kind=Parameter.KEYWORD_ONLY)
            seen[param.name] = param
            parameters.append(param)

        for loader in loaders:
            for param in signature(loader).parameters.values():
                add_param(param)
        if metadata_loader:
            for param in signature(metadata_loader).parameters.values():
                add_param(param)

        return Signature(parameters=parameters)

    @staticmethod
    async def _execute_loader(
        *,
        controller: Any,
        loader: Callable,
        params_model: type[BaseModel] | None,
        params_instance: BaseModel | None,
        request: Request | None,
        values: dict[str, Any] | None,
        body_values: dict[str, Any] | None,
    ) -> Any:
        sig = signature(loader)
        kwargs: dict[str, Any] = {}
        provided_values = values or {}

        def wants_request(param: Parameter) -> bool:
            if param.annotation is Request:
                return True
            if param.name == "request":
                return True
            return False

        dependency_values: dict[str, Any] | None = None

        async def resolve_dependencies():
            nonlocal dependency_values
            if dependency_values is not None:
                return dependency_values
            dependency_fn = isolate_dependency_only_function(loader)
            async with get_function_dependencies(
                callable=dependency_fn,
                url=getattr(controller, "url", None),
                request=request,
            ) as values:
                dependency_values = values
            return dependency_values

        def matches_params_model(param: Parameter) -> bool:
            if params_instance is None or params_model is None:
                return False
            if param.annotation is Parameter.empty:
                return param.name == "params"
            annotation = param.annotation
            # Handle string annotations (from deferred evaluation)
            if isinstance(annotation, str):
                return annotation == params_model.__name__
            # Direct comparison with the params_model class
            if annotation is params_model:
                return True
            if annotation == params_model:
                return True
            # isinstance check for when annotation is a class type
            if isclass(annotation) and isinstance(params_instance, annotation):
                return True
            # Check by class name as fallback (handles cross-module class definitions)
            if (
                isclass(annotation)
                and hasattr(annotation, "__name__")
                and annotation.__name__ == params_model.__name__
                and issubclass(annotation, BaseModel)
                and issubclass(params_model, BaseModel)
            ):
                return True
            origin = get_origin(annotation)
            if origin is None:
                return False
            if origin is Annotated:  # type: ignore[name-defined]
                args = get_args(annotation)
                if not args:
                    return False
                return matches_params_model(
                    param.replace(annotation=args[0])
                )
            args = get_args(annotation)
            return params_model in args

        for name, param in sig.parameters.items():
            if name in provided_values and name not in {"params", "request"}:
                kwargs[name] = provided_values[name]
                continue

            if matches_params_model(param):
                kwargs[name] = params_instance
                continue

            if wants_request(param):
                if request is None:
                    raise ValueError("Request object is not available")
                kwargs[name] = request
                continue

            if isinstance(param.default, fastapi_params.Depends):
                dependency_values = await resolve_dependencies()
                if name in dependency_values:
                    kwargs[name] = dependency_values[name]
                    continue

            if isinstance(param.default, fastapi_params.Header):
                kwargs[name] = RenderResolver._read_header_value(
                    param=param,
                    request=request,
                )
                continue

            if isinstance(
                param.default,
                (fastapi_params.Body, fastapi_params.Form, fastapi_params.File),
            ):
                if body_values is None:
                    raise RequestValidationError(
                        errors=[
                            RequestValidationFailure(
                                error_type="missing",
                                location=["body", name],
                                message="Body data not provided",
                                value_input=None,
                            )
                        ]
                    )
                if name not in body_values:
                    default_value = getattr(param.default, "default", None)
                    if default_value is not fastapi_params.Undefined:
                        kwargs[name] = default_value
                        continue
                    raise RequestValidationError(
                        errors=[
                            RequestValidationFailure(
                                error_type="missing",
                                location=["body", name],
                                message="Field required",
                                value_input=None,
                            )
                        ]
                    )
                value = body_values[name]
                kwargs[name] = RenderResolver._coerce_value(
                    annotation=param.annotation,
                    value=value,
                    location_prefix=["body", name],
                )
                continue

            if param.default is not Parameter.empty:
                kwargs[name] = param.default
                continue

            raise ValueError(
                f"Unsupported parameter in loader {loader.__name__}: {name}"
            )

        response = loader(**kwargs)
        if isawaitable(response):
            response = await response

        if isinstance(response, JSONResponse):
            if not isinstance(response.body, bytes):
                raise ValueError("Unable to parse JSONResponse body")
            return json_loads(response.body)

        if isinstance(response, Response):
            raise ValueError("Only JSONResponse is supported for loader responses")

        return response

    @staticmethod
    def _build_params_instance(
        *,
        params_model: type[BaseModel] | None,
        request: Request | None,
        values: dict[str, Any] | None,
    ) -> BaseModel | None:
        if params_model is None:
            return None

        payload: dict[str, Any] = {}
        if request is not None:
            payload.update(RenderResolver._read_query_params(request))
            payload.update(request.path_params)
        elif values is not None:
            payload.update(
                {key: values[key] for key in params_model.model_fields if key in values}
            )
        else:
            payload = {}

        try:
            return params_model.model_validate(payload)
        except ValidationError as exc:
            raise RenderResolver._build_validation_error(exc) from exc

    @staticmethod
    def _build_validation_error(exc: ValidationError) -> RequestValidationError:
        return RequestValidationError(
            errors=[
                RequestValidationFailure(
                    error_type=error["type"],
                    location=[str(part) for part in error.get("loc", [])],
                    message=error["msg"],
                    value_input=error.get("input"),
                )
                for error in exc.errors()
            ]
        )

    @staticmethod
    async def _read_body_values(request: Request) -> dict[str, Any] | None:
        if request is None:
            return None

        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                payload = await request.json()
            except Exception:
                return None
            if isinstance(payload, dict):
                return payload
            return None

        if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            payload: dict[str, Any] = {}
            for key, value in form.multi_items():
                if key in payload:
                    existing = payload[key]
                    if isinstance(existing, list):
                        existing.append(value)
                    else:
                        payload[key] = [existing, value]
                else:
                    payload[key] = value
            return payload

        return None

    @staticmethod
    def _read_query_params(request: Request) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in request.query_params.multi_items():
            if key in payload:
                existing = payload[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    payload[key] = [existing, value]
            else:
                payload[key] = value
        return payload

    @staticmethod
    def _read_header_value(param: Parameter, request: Request | None) -> Any:
        if request is None:
            raise ValueError("Request object is not available")
        header_param = param.default
        header_name = getattr(header_param, "alias", None) or param.name
        if getattr(header_param, "convert_underscores", True):
            header_name = header_name.replace("_", "-")
        value = request.headers.get(header_name)
        if value is None:
            default_value = getattr(header_param, "default", None)
            if default_value is not fastapi_params.Undefined:
                value = default_value
        return RenderResolver._coerce_value(
            annotation=param.annotation,
            value=value,
            location_prefix=["header", header_name],
        )

    @staticmethod
    def _coerce_value(
        *,
        annotation: Any,
        value: Any,
        location_prefix: list[str],
    ) -> Any:
        if annotation is Parameter.empty or annotation is Any:
            return value
        try:
            adapter = TypeAdapter(annotation)
            return adapter.validate_python(value)
        except ValidationError as exc:
            errors = []
            for error in exc.errors():
                loc = location_prefix + [str(part) for part in error.get("loc", [])]
                errors.append(
                    RequestValidationFailure(
                        error_type=error["type"],
                        location=loc,
                        message=error["msg"],
                        value_input=error.get("input"),
                    )
                )
            raise RequestValidationError(errors=errors) from exc

    @staticmethod
    def _get_page_request(
        controller: Any,
        request: Request | None,
    ) -> Request | None:
        if request is None:
            return None

        referer = request.headers.get("referer")
        if referer:
            parsed_path = urlparse(referer)
            scope = {
                **request.scope,
                "path": parsed_path.path,
                "query_string": parsed_path.query.encode(),
            }
        else:
            scope = dict(request.scope)

        view_request = Request(scope)

        if controller is None:
            return view_request

        def match_router(router) -> bool:
            for route in router.routes:
                match, child_scope = route.matches(view_request.scope)
                if match == Match.FULL:
                    view_request.scope = {
                        "path_params": {},
                        **view_request.scope,
                        **child_scope,
                    }
                    return True
            return False

        definition = getattr(controller, "_definition", None)
        render_router = None
        if definition and definition.route:
            render_router = definition.route.render_router

        if render_router and match_router(render_router):
            return view_request

        if definition:
            to_visit = list(definition.children)
            while to_visit:
                child = to_visit.pop(0)
                if child.route and child.route.render_router:
                    if match_router(child.route.render_router):
                        return view_request
                to_visit.extend(child.children)

        return view_request
