from flask import Flask, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route("/user/<int:user_id>/threads")
def user_threads_rewrite(user_id):
    """This mimics the Render rewrite for testing threads page locally"""
    return send_from_directory('.', 'threads.html')

@app.route('/')
def root():
    """Serves the index.html file for the root URL."""
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    # Runs the server on port 8001
    app.run(port=8001, debug=True)
