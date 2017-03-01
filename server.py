import argparse
import os, sys

import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.ioloop import PeriodicCallback
import json

from wlm import WavelengthMeter

# all connected browsers will be here
clients = []

def send_data():
    if len(clients)>0:
        data = wlmeter.wavelengths
        for c in clients:
            c.write_message(json.dumps(data))

class WsHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        clients.append(self)

    def on_close(self):
        clients.remove(self)
        print('connection closed')

    # to allow cross-domain connections
    def check_origin(self, origin):
        return True

class ApiHandler(tornado.web.RequestHandler):
    def get(self, channel=None):
        w = wlmeter.wavelengths
        sw = wlmeter.switcher_mode
        if channel is None:
            self.write({ "wavelengths": w, "switcher_mode": sw })
        else:
            ch = int(channel)
            if ch >=0 and ch<len(w):
                self.write("%.8f" % w[ch])
            else:
                self.set_status(400)
                self.write({"error":"Wrong channel"})

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html",
            wavelengths=wlmeter.wavelengths,
            **get_config()
        )


default_config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "config.json"))

def make_app(config):
    static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
    return tornado.web.Application([
            (r"%s" % config["root"], IndexHandler),
            (r"%sapi/" % config["root"], ApiHandler),
            (r"%sapi/(\d)/" % config["root"], ApiHandler),
            (r"%sws/" % config["root"], WsHandler),
            (r"%sstatic/(.*)" % config["root"], tornado.web.StaticFileHandler, {'path': static_path}),
    ], debug=True)

# config file parser
class config_action(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        config_file = values
        if not os.path.isfile(config_file):
            raise argparse.ArgumentTypeError("config:{0} is not a valid file".format(config_file))
        if os.access(config_file, os.R_OK):
            setattr(namespace, self.dest, config_file)
        else:
            raise argparse.ArgumentTypeError("config:{0} is not a readable file".format(config_file))

# building configuration
def get_config():
    # command line arguments parsing
    parser = argparse.ArgumentParser(description='Starts a webserver with wavemeter interface.')
    parser.add_argument('--debug', dest='debug', action='store_const',
                        const=True,
                        help='runs the script in debug mode simulating wavelength values')
    parser.add_argument('-c', '--config', action=config_action, default=default_config_file,
                        help='path to config json file, default: config.json in the script folder')
    parser.add_argument('port', type=int, nargs='?',
                        help='server port, default: 8000')

    args = parser.parse_args()

    # default configuration
    config = {
        "port": 8000, # port
        "root": "/", # path
        "precision": 5, # number of decimals in wavelength display
        "update_rate": 0.1, # how often updates will be sent to the browsers
        "debug": False, # do you want to work with real wavemeter or to test run it?
        "channels": [{"i": i, "label": "Channel %d" % (i+1)} for i in range(8)] # channels to display
    }

    # configuration from the file
    with open(args.config, "r") as f:
        config.update(json.loads(f.read()))

    # configuration from command line
    if args.port == None:
        args.port = config["port"]
    config.update(vars(args))

    return config

if __name__ == "__main__":

    config = get_config()

    wlmeter = WavelengthMeter(debug=config["debug"])

    app = make_app(config)
    app.listen(config["port"])
    print("Server started at http://localhost:%d%s" % (config["port"], config["root"]))

    # periodic callback takes update rate in ms
    PeriodicCallback(send_data, config["update_rate"]*1000).start()

    tornado.ioloop.IOLoop.instance().start()

