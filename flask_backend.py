import re

from cloudwrapper.btq import BtqConnection
from collections import defaultdict
from flask import current_app
from flask_script import Command
from functools import wraps
from queue import Empty
from signal import SIGINT, SIGTERM, signal
from threading import Lock


class Backend:

    def __init__(self, app=None):
        self.connection = None
        self.before_first_task_callbacks = defaultdict(list)
        self.handlers = {}
        self.queues = {}
        self.lock = Lock()
        self.stopped = True
        self.app = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        app.extensions['backend'] = self
        match = re.match(
            r'^btq://([-.\w]+)(?::(\d+))?$',
            app.config['BACKEND_CONNECTION_URI'])
        host = match.group(1)
        port = match.group(2)
        self.connection = BtqConnection(
            host=host,
            port=int(port) if port else 11300)

    def before_first_task(self, queue_name):
        def decorator(callback):
            self.before_first_task_callbacks[queue_name].append(callback)
            return callback
        return decorator

    def receiver(self, queue_name):
        def decorator(callback):
            self.handlers[queue_name] = callback
            return callback
        return decorator

    def send(self, queue_name, message):
        with self.lock:
            queue = self.queues.get(queue_name)
            if queue is None:
                queue = self.connection.queue(queue_name)
                self.queues[queue_name] = queue
            queue.put(message)

    def task(self, queue_name, endpoint=None):
        def decorator(callback):
            @wraps(callback)
            def wrapper(*args, **kwargs):
                self.send(queue_name, {
                    'endpoint': endpoint,
                    'args': args,
                    'kwargs': kwargs,
                })
            nonlocal endpoint
            if endpoint is None:
                endpoint = callback.__name__
            router = self.handlers.get(queue_name)
            if router is None:
                router = Router()
                self.handlers[queue_name] = router
            router[endpoint] = callback
            return wrapper
        return decorator

    def run(self, queue_name):
        self.app.logger.info('Starting backend %s', queue_name)
        for callback in self.before_first_task_callbacks[queue_name]:
            callback()
        handler = self.handlers[queue_name]
        queue = self.connection.queue(queue_name)
        self.stopped = False
        signal(SIGINT, lambda signo, frame: self.stop())
        signal(SIGTERM, lambda signo, frame: self.stop())
        while not self.stopped:
            try:
                task = queue.get(block=False, timeout=8)
            except Empty:
                continue
            handler(task)
            queue.task_done()
        self.app.logger.info('Terminating backend %s', queue_name)

    def stop(self):
        self.stopped = True


class Router:

    def __init__(self):
        self.callbacks = {}

    def __setitem__(self, endpoint, callback):
        self.callbacks[endpoint] = callback

    def __call__(self, task):
        callback = self.callbacks[task['endpoint']]
        callback(*task['args'], **task['kwargs'])


@Command
def BackendCommand(queue_name):
    current_app.extensions['backend'].run(queue_name)
