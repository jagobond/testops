"""Child process: serve the product on a port the kernel chooses, and say which one.

The suite must talk to the socket this process opened. Choosing a port in the parent and passing it
would race another binder (on Windows ``SO_REUSEADDR`` lets a second process receive the traffic),
so the child binds port 0, prints ``PORT <n>``, and the parent connects only to that number.
"""
from http.server import ThreadingHTTPServer

from testops.store import db
from testops.web.app import Handler

db.connect().close()
httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
print("PORT", httpd.server_address[1], flush=True)
httpd.serve_forever()
