from setuptools import setup, find_packages

setup(
    name='wsmonitor',
    version='0.1.0',
    description='Sample package for Python-Guide.org',
    author='Mark Weinreuter',
    packages=find_packages(exclude=('tests', 'examples'))
)