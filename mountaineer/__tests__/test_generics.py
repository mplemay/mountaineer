from mountaineer.generics import expand_typevars, get_typevar_mapping


class Base[T]:
    pass


class Intermediate[T, K](Base[T]):
    pass


class Final(Intermediate[int, str]):
    pass


def test_get_typevar_mapping():
    mapping = get_typevar_mapping(Final)

    # With PEP 695, we need to get the type parameters from the class
    # Base has T, Intermediate has T and K - they're different T objects
    base_T = Base.__type_params__[0]  # type: ignore
    intermediate_T = Intermediate.__type_params__[0]  # type: ignore
    K = Intermediate.__type_params__[1]  # type: ignore

    # The mapping should contain both T parameters and K
    assert mapping == {
        base_T: intermediate_T,  # Base's T maps to Intermediate's T
        intermediate_T: int,  # Intermediate's T maps to int
        K: str,  # K maps to str
    }


def test_expand_typevars():
    # With PEP 695, we need to get the type parameters from the class
    intermediate_T = Intermediate.__type_params__[0]  # type: ignore
    K = Intermediate.__type_params__[1]  # type: ignore

    assert expand_typevars(
        {
            K: intermediate_T,
            intermediate_T: int,
        },
    ) == {
        K: int,
        intermediate_T: int,
    }
