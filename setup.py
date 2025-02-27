from setuptools import setup, find_packages

setup(
    name='wsmonitor',
    version='0.1.0',
    description='Websocket interface for process control',
    author='Mark Weinreuter',
    packages=find_packages(exclude=('tests', 'examples')),
    entry_points={
        'console_scripts': [
            'wsmonitor=wsmonitor.cli:cli',
        ],
    },

)