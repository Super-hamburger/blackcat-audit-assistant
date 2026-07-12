def register(app):
    return {
        "name": "Example Plugin",
        "actions": [
            {
                "id": "hello",
                "title": "Hello Plugin",
                "description": "This is an example plugin action."
            }
        ]
    }
