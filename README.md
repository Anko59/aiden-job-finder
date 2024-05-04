# Aiden App

Aiden (AI-Driven Employment Navigator) is a Django-based web application that uses the Mistral AI model for chat interactions. It also includes tools for CV editing and job scraping from Indeed.

## Features

- Chat interface with the Mistral AI model
- CV editing tool
- Job scraping tool from Indeed

## File Structure

Here's a brief overview of the main files in the project:

- `aiden_app/agents/mistral_agent.py`: This file contains the `MistralAgent` class which handles the interaction with the Mistral AI model. It also includes the `MistralAgentToolOnly` class which is a variant of `MistralAgent`.

- `aiden_app/views.py`: This file contains the Django views for the application. It includes the `chat_view` function which handles the chat interactions.

- `aiden_app/templates/chat.html`: This is the main HTML template for the chat interface. It includes a form for user input and displays the chat messages.

- `aiden_app/static/js/main.js`: This is the main JavaScript file for the application. It handles the client-side logic of the chat interface.

The `aiden_app/tools/utils/` directory contains utility functions and classes used by the tools. For example, `aiden_app/tools/utils/cv_editor.py` contains the `CVEdit` and `CVEditor` classes used by `CVEditorTool`.

## Installation

You need to modify the `.env` file to include your MISTRAL_API_KEY value:

```
MISTRAL_API_KEY=your_mistral_api_key
```

Once set you can lauch the app with
```bash
make up
```
If you apply changes locally you need to rebuild the app

```
make build
```

## Usage

After successfully installing and starting the Aiden App, you can interact with it through your web browser. Here are the steps:

1. Open your web browser and navigate to `aiden.dev.localhost`.
2. Select a profile to start a chat session.
3. You can now interact with the AI agent in the chat interface. The agent can perform various tasks based on your requests. For example, you can ask the agent to:
   - Search for job openings: "Search for data engineering jobs in Paris."
   - Edit your CV to fit a specific job description: "Edit my CV to fit the description of the position at Deezer."

Remember, the AI agent is designed to understand natural language, so feel free to phrase your requests in the way that feels most natural to you.

## Contributing
If you would like to contribute, please follow these steps:

1. Fork the repository on GitHub.
2. Clone your forked repository to your local machine.
3. Create a new branch for your feature or bug fix.
4. Make your changes and commit them with descriptive commit messages.
5. Push your branch to your forked repository on GitHub.
6. Submit a pull request to the main repository.

Please ensure that your code follows the project's coding conventions and includes appropriate tests. Also, make sure to provide a clear description of your changes in the pull request.

Thank you for your contribution!

## Future Features
Here are some planned future features for the Aiden App:
- Profile creation for new users
- Improved front-end and back-end code quality
- Cover letter templating functionality
- Enhanced prompt engineering for better chat interactions
- User sessions to maintain context across multiple interactions
- Continuous Integration and Continuous Deployment (CI/CD) pipeline for automated testing and deployment
- Redis integration for caching the AI model and job scrapers
- Addition of more job sourcing tools for comprehensive job search

We are continuously working on improving the Aiden App and adding new features. Stay tuned for updates!
