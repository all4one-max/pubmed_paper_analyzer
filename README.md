## Setup Instructions

1. Clone the Repository First, clone the repository to your local machine:
```bash
git clone <repository_url>
```

2. Create a .env File In the root directory, create a .env file and copy the contents from .env.template into it. Fill in the environment variables with the appropriate values (e.g., API keys, paths, etc.).

3. Install Dependencies Open your terminal and navigate to the project directory. Then, activate the virtual environment using:
```
pipenv shell
pipenv install
```

4. Select Python Interpreter in VS Code In VS Code, ensure you select the correct Python interpreter that corresponds to the virtual environment. You can do this by opening the Command Palette (Ctrl+Shift+P), then selecting Python: Select Interpreter and choosing the one linked to your pipenv environment.

5. Run the FastAPI Server You can now run the FastAPI server directly from VS Code. A launch.json configuration is already provided for ease of execution. Press F5 or use the Run button to start the server.