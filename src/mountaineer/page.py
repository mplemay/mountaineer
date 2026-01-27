from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, isclass, signature
from pathlib import Path
from typing import Annotated, Any, Callable, Iterable, get_args, get_origin

from fastapi import Request, params as fastapi_params
from fastapi.responses import Response
from inflection import camelize
from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo

from mountaineer.actions.action_dec import action as action_dec
from mountaineer.annotation_helpers import MountaineerUnsetValue
from mountaineer.controller import ControllerBase
from mountaineer.controller_layout import LayoutControllerBase
from mountaineer.render import Metadata, RenderBase
from mountaineer.render_resolver import RenderResolver


@dataclass(slots=True, kw_only=True, frozen=True)
class DataDefinition:
    name: str
    func: Callable
    return_type: type
    ssr: bool


class Page:
    def __init__(
        self,
        *,
        view: Path,
        path: str | None = None,
        params: type[BaseModel] | None = None,
        name: str | None = None,
        layout: bool = False,
    ) -> None:
        if layout:
            if path:
                raise ValueError("Layout pages cannot specify a path")
        elif not path:
            raise ValueError("Non-layout pages require a path")

        self.view = view
        self.path = path
        self.params = params
        self.layout = layout

        self.name = name or camelize(view.stem)

        self._data_defs: list[DataDefinition] = []
        self._data_by_name: dict[str, DataDefinition] = {}
        self._action_defs: list[Callable] = []
        self._action_updates: dict[Callable, tuple[Callable, ...] | None] = {}
        self._metadata_loader: Callable | None = None

    def data(
        self,
        *,
        ssr: bool = True,
        name: str | None = None,
    ) -> Callable[[Callable], Callable]:
        def wrapper(func: Callable) -> Callable:
            typehinted_response = func.__annotations__.get(
                "return", MountaineerUnsetValue()
            )
            if isinstance(typehinted_response, MountaineerUnsetValue):
                raise ValueError(
                    f"Loader {func.__name__} must have a return type annotation"
                )

            loader_name = name or func.__name__
            if loader_name in self._data_by_name:
                raise ValueError(f"Duplicate loader name: {loader_name}")

            self._validate_loader_signature(func=func, ssr=ssr)

            return_type = typehinted_response
            if isclass(return_type) and issubclass(return_type, Response):
                return_type = Any

            data_def = DataDefinition(
                name=loader_name,
                func=func,
                return_type=return_type,
                ssr=ssr,
            )

            self._data_defs.append(data_def)
            self._data_by_name[loader_name] = data_def
            return func

        return wrapper

    def metadata(self, func: Callable | None = None) -> Callable:
        def wrapper(target: Callable) -> Callable:
            if self._metadata_loader is not None:
                raise ValueError("Only one metadata loader is allowed per page")

            typehinted_response = target.__annotations__.get(
                "return", MountaineerUnsetValue()
            )
            if typehinted_response != Metadata:
                raise ValueError("Metadata loader must return Metadata")

            self._metadata_loader = target
            return target

        if func is not None:
            return wrapper(func)
        return wrapper

    def action(
        self,
        func: Callable | None = None,
        *,
        update: Iterable[Callable] | None = None,
        response_model: type | None = None,
        exception_models: list[type] | None = None,
        raw_response: bool | None = None,
    ) -> Callable:
        update_tuple = tuple(update) if update else None
        if update_tuple:
            for loader in update_tuple:
                if loader not in {data_def.func for data_def in self._data_defs}:
                    raise ValueError(
                        f"Update target {loader} is not registered on this page"
                    )

        def wrapper(target: Callable) -> Callable:
            bound_target = self._bind_action_target(target)
            wrapped = action_dec(
                update=update_tuple,
                response_model=response_model,
                exception_models=exception_models,
                raw_response=raw_response,
            )(bound_target)
            self._action_defs.append(wrapped)
            self._action_updates[wrapped] = update_tuple
            return wrapped

        if func is not None:
            return wrapper(func)
        return wrapper

    def _bind_action_target(self, target: Callable) -> Callable:
        target_sig = signature(target)
        params = list(target_sig.parameters.values())
        if params and params[0].name == "self":
            return target

        def bound(self, *args, **kwargs):
            return target(*args, **kwargs)

        bound.__name__ = target.__name__
        bound.__qualname__ = target.__qualname__
        bound.__module__ = target.__module__
        bound.__annotations__ = dict(getattr(target, "__annotations__", {}))
        bound.__signature__ = target_sig.replace(
            parameters=[
                Parameter("self", kind=Parameter.POSITIONAL_OR_KEYWORD)
            ]
            + params
        )
        return bound

    def build(self) -> ControllerBase | LayoutControllerBase:
        render_model = self._build_render_model()
        action_map = {action.__name__: action for action in self._action_defs}

        async def render(self, **kwargs) -> render_model:  # type: ignore[name-defined]
            request = kwargs.get("request")
            values = {key: value for key, value in kwargs.items() if key != "request"}
            return await RenderResolver.resolve(
                controller=self,
                request=request,
                values=values,
                metadata_loader=getattr(self, "_page_metadata_loader", None),
            )

        render.__annotations__["return"] = render_model
        render.__signature__ = RenderResolver.build_signature(  # type: ignore[attr-defined]
            loaders=[data_def.func for data_def in self._data_defs if data_def.ssr],
            metadata_loader=self._metadata_loader,
        ).replace(return_annotation=render_model)

        attributes: dict[str, Any] = {
            "view_path": self.view.as_posix(),
            "render": render,
            "_page_data_defs": self._data_defs,
            "_page_params_model": self.params,
            "_page_metadata_loader": self._metadata_loader,
            "_page_render_model": render_model,
            **action_map,
        }
        if not self.layout:
            attributes["url"] = self.path

        base_cls: type[ControllerBase]
        if self.layout:
            base_cls = LayoutControllerBase
        else:
            base_cls = ControllerBase

        controller_cls = type(self.name, (base_cls,), attributes)
        controller = controller_cls()

        for action, update_targets in self._action_updates.items():
            if not update_targets:
                continue
            update_fields = []
            for loader in update_targets:
                data_def = next(
                    (data_def for data_def in self._data_defs if data_def.func == loader),
                    None,
                )
                if data_def is None:
                    continue
                update_fields.append(getattr(render_model, data_def.name))
            if update_fields:
                metadata = getattr(action, "_mountaineer_metadata", None)
                if metadata is not None:
                    metadata.reload_states = tuple(update_fields)

        return controller

    def _build_render_model(self) -> type[RenderBase]:
        fields: dict[str, tuple[Any, FieldInfo]] = {}
        for data_def in self._data_defs:
            annotation = data_def.return_type
            if not data_def.ssr:
                annotation = self._make_optional(annotation)
                field_info = FieldInfo(default=None)
            else:
                field_info = FieldInfo.from_annotation(annotation=annotation)
            fields[data_def.name] = (annotation, field_info)

        model_name = f"{self.name}Render"
        render_model = create_model(
            model_name,
            __base__=RenderBase,
            __module__=self._get_module_name(),
            **fields,
        )
        return render_model

    def _make_optional(self, annotation: Any) -> Any:
        if annotation is None:
            return None
        if getattr(annotation, "__origin__", None) is None:
            return annotation | None
        if annotation in {Any, object}:
            return annotation
        return annotation | None

    def _validate_loader_signature(self, *, func: Callable, ssr: bool) -> None:
        params_model = self.params
        loader_sig = signature(func)

        def matches_params(annotation: Any) -> bool:
            if params_model is None:
                return False
            if annotation is Parameter.empty:
                return True
            if annotation is params_model:
                return True
            origin = get_origin(annotation)
            if origin is Annotated:
                args = get_args(annotation)
                if not args:
                    return False
                return matches_params(args[0])
            if origin is None:
                return False
            return params_model in get_args(annotation)

        for param in loader_sig.parameters.values():
            if param.kind in {Parameter.VAR_KEYWORD, Parameter.VAR_POSITIONAL}:
                raise ValueError(
                    f"Loader {func.__name__} uses variadic parameters which are not supported"
                )

            if param.name == "params":
                if params_model is None:
                    raise ValueError(
                        f"Loader {func.__name__} declared params but page has no params model"
                    )
                if not matches_params(param.annotation):
                    raise ValueError(
                        f"Loader {func.__name__} params type must be {params_model}"
                    )
                continue

            if (
                param.annotation is Request
                or param.name == "request"
            ):
                if self.layout:
                    raise ValueError(
                        f"Layout loader {func.__name__} cannot accept Request"
                    )
                continue

            if isinstance(param.default, fastapi_params.Depends):
                continue

            if isinstance(param.default, fastapi_params.Header):
                continue

            if isinstance(
                param.default,
                (fastapi_params.Body, fastapi_params.Form, fastapi_params.File),
            ):
                if ssr:
                    raise ValueError(
                        f"Loader {func.__name__} uses Body/Form/File but is marked ssr=True"
                    )
                if self.layout:
                    raise ValueError(
                        f"Layout loader {func.__name__} cannot accept Body/Form/File"
                    )
                continue

            raise ValueError(
                f"Loader {func.__name__} must use params/Depends/Request/Header or Body/Form/File"
            )

    def _get_module_name(self) -> str:
        return self.__class__.__module__
