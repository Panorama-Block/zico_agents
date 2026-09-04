import ast
import unittest
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "src" / "app.py"


def _load_tree():
    return ast.parse(APP_PATH.read_text())


def _function(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"Function {name!r} not found")


def _argument_names(function):
    args = function.args
    return {
        *(arg.arg for arg in args.posonlyargs),
        *(arg.arg for arg in args.args),
        *(arg.arg for arg in args.kwonlyargs),
    }


def _source_segment(node):
    source = APP_PATH.read_text()
    segment = ast.get_source_segment(source, node)
    if segment is None:
        raise AssertionError("Unable to extract function source")
    return segment


def _route_paths(tree):
    routes = []

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            func = decorator.func
            if not isinstance(func, ast.Attribute):
                continue

            if not isinstance(func.value, ast.Name):
                continue

            if func.value.id != "app":
                continue

            if func.attr not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }:
                continue

            if not decorator.args:
                continue

            path_arg = decorator.args[0]
            if not isinstance(path_arg, ast.Constant):
                continue

            routes.append(
                (
                    func.attr.upper(),
                    path_arg.value,
                    node.name,
                )
            )

    return routes


class ChatAppOwnershipContractTest(unittest.TestCase):
    def test_direct_unsecured_history_routes_do_not_exist(self):
        tree = _load_tree()
        routes = _route_paths(tree)

        self.assertNotIn(
            ("GET", "/chat/messages", "get_messages"),
            routes,
        )
        self.assertNotIn(
            ("GET", "/chat/conversations", "get_conversations"),
            routes,
        )

    def test_chat_endpoint_requires_authenticated_principal(self):
        tree = _load_tree()
        function = _function(tree, "chat")

        self.assertIn(
            "principal",
            _argument_names(function),
        )

        source = _source_segment(function)

        self.assertIn(
            "_resolve_identity(",
            source,
        )
        self.assertIn(
            "principal,",
            source,
        )

    def test_chat_stream_requires_authenticated_principal(self):
        tree = _load_tree()
        function = _function(tree, "chat_stream")

        self.assertIn(
            "principal",
            _argument_names(function),
        )

        source = _source_segment(function)

        self.assertIn(
            "_resolve_identity(",
            source,
        )
        self.assertIn(
            "principal,",
            source,
        )

    def test_chat_stream_with_files_requires_authenticated_principal(self):
        tree = _load_tree()
        function = _function(tree, "chat_stream_with_files")

        self.assertIn(
            "principal",
            _argument_names(function),
        )

        source = _source_segment(function)

        self.assertIn(
            "principal.user_id",
            source,
        )

    def test_chat_audio_requires_authenticated_principal(self):
        tree = _load_tree()
        function = _function(tree, "chat_audio")

        self.assertIn(
            "principal",
            _argument_names(function),
        )

        source = _source_segment(function)

        self.assertIn(
            "principal.user_id",
            source,
        )

    def test_resolve_identity_does_not_authorise_request_user_id_or_wallet(self):
        tree = _load_tree()
        function = _function(tree, "_resolve_identity")
        source = _source_segment(function)

        self.assertIn(
            "principal.user_id",
            source,
        )

        self.assertNotIn(
            "request.user_id",
            source,
        )

        self.assertNotIn(
            'f"wallet::',
            source,
        )


if __name__ == "__main__":
    unittest.main()
