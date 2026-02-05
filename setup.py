from setuptools import setup, find_packages
import os

# 读取版本号
with open(os.path.join("svd_tool", "__init__.py"), "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"').strip("'")
            break
    else:
        version = "2.1.0"

# 读取README
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="svd-editor",
    version=version,
    author="SVD Tool Team",
    author_email="",
    description="A CMSIS SVD parsing/editing/visualization tool based on componentized architecture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SamyiHu/SVDEditor",
    packages=find_packages(include=["svd_tool", "svd_tool.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Embedded Systems",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
    ],
    python_requires=">=3.10",
    install_requires=[
        "PyQt6>=6.5.0",
    ],
    entry_points={
        "console_scripts": [
            "svd-editor=svd_tool.main:main",
        ],
        "gui_scripts": [
            "svd-editor-gui=svd_tool.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "svd_tool": [],
    },
)