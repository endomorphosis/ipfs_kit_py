import textwrap

class TestDashboard:
    def _app_js(self) -> str:
        import textwrap
        helpers = textwrap.dedent("""
        let test = 'hello';
        """)
        js_code = helpers + r"""
        (function(){
            console.log('test');
        })();
        """
        js_code = textwrap.dedent(js_code)
        js_code = ''.join(c for c in js_code if ord(c) < 128)
        return js_code

    def _mcp_client_js(self) -> str:
        return """
        console.log('client');
        """

if __name__ == "__main__":
    dashboard = TestDashboard()
    print("App JS:", len(dashboard._app_js()), "chars")
    print("Client JS:", len(dashboard._mcp_client_js()), "chars")
