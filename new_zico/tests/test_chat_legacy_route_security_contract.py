import ast
import unittest
from pathlib import Path


ROUTES_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "routes"
    / "chat_manager_routes.py"
)


def _route_paths():
    tree = ast.parse(ROUTES_PATH.read_text())
    routes = []

    for node in tree.body:
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            func = decorator.func
            if not isinstance(func, ast.Attribute):
                continue

            if not isinstance(func.value, ast.Name):
                continue

            if func.value.id != "router":
                continue

            if not decorator.args:
                continue

            path = decorator.args[0]
            if not isinstance(path, ast.Constant):
                continue

            routes.append(
                (
                    func.attr.upper(),
                    path.value,
                    node.name,
                )
            )

    return routes


class LegacyChatRouteSecurityContractTest(unittest.TestCase):
    def test_unauthenticated_state_changing_clear_route_is_not_exposed(self):
        self.assertNotIn(
            ("GET", "/clear", "clear_messages"),
            _route_paths(),
        )

    def test_user_population_route_is_not_exposed(self):
        self.assertNotIn(
            ("GET", "/users", "get_users"),
            _route_paths(),
        )


if __name__ == "__main__":
    unittest.main()
