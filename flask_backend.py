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
        self.callbacks = defaultdict(dict)
        self.queues = {}
        self.lock = Lock()
        self.stopped = True
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
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
            self.callbacks[queue_name][endpoint] = callback
            return wrapper
        return decorator

    def run(self, queue_name):
        app = current_app._get_current_object()
        for callback in self.before_first_task_callbacks[queue_name]:
            callback()
        app.logger.info('Starting backend %s', queue_name)
        queue = self.connection.queue(queue_name)
        self.stopped = False
        signal(SIGINT, self.stop)
        signal(SIGTERM, self.stop)
        while not self.stopped:
            try:
                task = queue.get(block=False, timeout=8)
            except Empty:
                continue
            with app.app_context():
                try:
                    self.call(queue_name, task)
                except Exception:
                    app.logger.exception('Exception occured')
                else:
                    queue.task_done()
        app.logger.info('Terminating backend %s', queue_name)

    def stop(self, signo=None, frame=None):
        self.stopped = True

    def send(self, queue_name, task):
        with self.lock:
            queue = self.queues.get(queue_name)
            if queue is None:
                queue = self.connection.queue(queue_name)
                self.queues[queue_name] = queue
            queue.put(task)

    def call(self, queue_name, task):
        callback = self.callbacks[queue_name][task['endpoint']]
        try:
            args = task['args']
        except KeyError:
            args = []
        try:
            kwargs = task['kwargs']
        except KeyError:
            kwargs = {}
        callback(*args, **kwargs)


@Command
def BackendCommand(queue_name):
    current_app.extensions['backend'].run(queue_name)
