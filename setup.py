from setuptools import setup

setup(
    name='Flask-Backend',
    version='1.3',
    description='Asynchronous backend tasks for Flask',
    py_modules=['flask_backend'],
    install_requires=[
        'Flask>=0.11',
        'Flask-Script>=2.0',
        'PyYAML>=3.11',
        'beanstalkc3>=0.4.0',
        'cloudwrapper>=1.7',
    ])
