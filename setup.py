from setuptools import setup, find_packages

setup(
    name="stock_tool",
    version="0.1.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": ["StockAgent=scripts.app:main"]
    },
    install_requires=["numpy", 
                      "pandas", 
                      "requests",
                      "pandas",
                      "fastapi",
                      "fastmcp",
                      "requests",
                      "dotenv",
                      "bs4",
                      "ta-lib"],
)
