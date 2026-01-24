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
    T = Base.__type_params__[0]  # type: ignore
    K = Intermediate.__type_params__[1]  # type: ignore

    assert mapping == {
        T: int,
        K: str,
    }


def test_expand_typevars():
    # With PEP 695, we need to get the type parameters from the class
    T = Base.__type_params__[0]  # type: ignore
    K = Intermediate.__type_params__[1]  # type: ignore

    assert expand_typevars(
        {
            K: T,
            T: int,
        },
    ) == {
        K: int,
        T: int,
    }
