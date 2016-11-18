"""the setup script for KVNDB."""
from setuptools import setup


def read_file(path, ignore=False):
    try:
        with open(path, "r") as f:
            return f.read()
    except IOError:
        if ignore:
            return "<ERROR READING FILE>"
        else:
            raise


setup(
    name="kvndb",
    version="0.1.2",
    description="A modular Key/Value Network Database server+client using twisted",
    long_description=read_file("README.md", ignore=True),
    author="bennr01",
    author_email="benjamin99.vogt@web.de",
    url="https://github.com/bennr01/kvndb/",
    license="MIT",
    packages=["kvndb"],
    zip_safe=False,
    install_requires=[
        "twisted",
        ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 2.7",
        "Topic :: Database",
        ],
    keywords="database key value network scalable",
    entry_points={
        "console_scripts": [
            "kvndb=kvndb.runner:run",
            ],
        },
    package_data={
        "": [
            "LICENSE",
            "README.md",
            ],
        },
    )
