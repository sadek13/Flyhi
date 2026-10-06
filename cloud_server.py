from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import os

RASA_URL = "http://127.0.0.1:5005/webhooks/rest/webhook"


class FlyHiHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/webhooks/rest/webhook":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            request = Request(
                RASA_URL,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urlopen(request) as response:
                    data = response.read()
                    self.send_response(response.status)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(data)
            except HTTPError as error:
                self.send_response(error.code)
                self.end_headers()
            except Exception as error:
                self.send_response(502)
                self.end_headers()
                self.wfile.write(str(error).encode())

        else:
            self.send_error(404)


os.chdir("/app/web")

server = ThreadingHTTPServer(("0.0.0.0", 7860), FlyHiHandler)
server.serve_forever()