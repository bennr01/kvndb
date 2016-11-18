"""the setup script for KVNDB."""
from setuptools import setup


def read_file(path):
    with open(path, "r") as f:
        return f.read()


setup(
    name="kvndb",
    version="0.1",
    description="A modular Key/Value Network Database server+client using twisted",
    long_description=read_file("README.md"),
    author="bennr01",
    author_email="benjamin99.vogt@web.de",
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
    )