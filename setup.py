from setuptools import setup, find_packages

# Find the agent package that contains the main module
packages = find_packages(".")

setup(
    name="munggoggo",
    version="0.1",
    description="agent system",
    url="",
    author="thomas.we.weber@gmx.de",
    author_email="thomas.we.weber@gmx.de",
    license="BSD3",
    packages=packages,
    zip_safe=False,
)
