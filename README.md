# Flask-Backend

Flask extension for asynchronous execution of backend tasks.

Decorate your task handlers with the `Backend.task()` decorator
just as you do with route handlers. Calling the decorated function
will then schedule execution of the function on a backend instance
that you start separately from your main application.

The extension communicates via Beanstalkd queues. You specify
the name of the queue to be used for each handler as an argument
to the `Backend.task()` decorator. Multiple handlers can use the
same queue. Only when you want to distinguish between different
runtime environments, eg. Docker images, should you use different
queues for each environment.

Arguments of the task function call are serialized to plain JSON.
That means you can't give the function as arguments custom class
instances. A typical scenario is that you pass a key to a database
table row as a string or number and the task reads data from the
database itself.

To start a backend instance you again specify the queue which it
will handle. You can use the integration with the `Flask-Script`
extension for that.

You can initialize your backend instances using the
`Backend.before_first_task()` decorator, similar to
`Flask.before_first_request()`.

## Configuration

- `BACKEND_CONNECTION_URI`: Address of the Beanstalkd instance, `btq://host[:port]`.

## Example

Assume we have the following code in a file called `example.py`.

```python
from flask import Flask, flash, render_template_string, request
from flask_backend import Backend, BackendCommand
from flask_script import Manager, Server

app = Flask(__name__)
app.config.from_object(...)

backend = Backend(app)
manager = Manager(app)


TEMPLATE = """\
<html>
<body>
{% for message in get_flashed_messages() %}
<p>{{ message }}</p>
{% endfor %}
<p>Click on the "SEND" button to schedule a task.</p>
<form action="" method="POST">
<input type="submit" value="SEND"/>
</form>
</body>
</html>
"""


@app.route('/', methods={'GET', 'POST'})
def index():
    if request.method == 'POST':
        hello('world')
        flash('Backend task scheduled, check logs.')
        return redirect(request.url)
    return render_template_string(TEMPLATE)


@backend.before_first_task('com.example/default')
def initialize():
    app.logger.info('Initializing backend.')


@backend.task('com.example/default')
def hello(target):
    app.logger.info('Hello, %s!', target)


manager.add_command('backend', BackendCommand)
manager.add_command('runserver', Server(host='0.0.0.0', port=8000))


if __name__ == '__main__':
    manager.run()
```

To start the application and the backend instances, run the following commands:

```shell
$ python example.py runserver
$ python example.py backend com.example/default
```
