from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta
import json
import os
import secrets

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-portfolio-secret-change-in-production")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("FLASK_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=3),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
)

MESSAGES_FILE = "messages.json"
ADMIN_CONFIG_FILE = "admin_config.json"
SITE_CONTENT_FILE = "site_content.json"
UPLOAD_DIR = os.path.join("static", "uploads")
CV_DIR = os.path.join("static", "uploads")
PROJECT_IMG_DIR = os.path.join("static", "uploads", "projects")

DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "abc_123")

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
ALLOWED_CV_EXT = {"pdf"}

for folder in (UPLOAD_DIR, PROJECT_IMG_DIR):
    os.makedirs(folder, exist_ok=True)

if not os.path.exists(MESSAGES_FILE):
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)


def load_admin_credentials():
    if os.path.exists(ADMIN_CONFIG_FILE):
        with open(ADMIN_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("username", DEFAULT_ADMIN_USERNAME), data.get("password", DEFAULT_ADMIN_PASSWORD)
    return DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD


def save_admin_credentials(username, password):
    with open(ADMIN_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"username": username, "password": password}, f, indent=4)


def verify_admin(username, password):
    admin_user, admin_pass = load_admin_credentials()
    return username == admin_user and password == admin_pass


def load_site_content():
    with open(SITE_CONTENT_FILE, "r", encoding="utf-8") as f:
        content = json.load(f)
    return ensure_site_structure(content)


DEFAULT_SETTINGS = {
    "nav": {
        "home": True,
        "about": True,
        "skills": True,
        "projects": True,
        "experience": True,
        "contact": True,
    },
    "hero": {
        "status_badge": True,
        "status_text": "Open for work",
        "typing_enabled": True,
        "typing_prefix": "I build ",
        "typing_strings": ["automation tools", "AI systems", "web apps", "ML pipelines"],
        "btn_primary": {"enabled": True, "label": "Projects", "url": "#projects"},
        "btn_secondary": {"enabled": True, "label": "Hire me", "url": "#contact"},
        "show_stats": True,
        "show_projects_stat": True,
        "show_visitors_stat": True,
        "show_cv_stat": True,
    },
    "social_rail": {
        "enabled": True,
        "github": True,
        "whatsapp": True,
        "email": True,
        "cv": True,
    },
    "projects_section": {
        "filters_enabled": True,
        "github_repos_enabled": True,
    },
    "contact_section": {
        "form_enabled": True,
        "show_email_card": True,
        "show_whatsapp_card": True,
        "show_github_card": True,
        "show_location_card": True,
    },
    "footer": {"enabled": True},
    "particles": {"enabled": True},
}


def deep_merge(base, override):
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def visible_items(items):
    return [x for x in items if x.get("visible", True)]


def ensure_site_structure(content):
    defaults = {
        "sections": {
            "about": {"label": "About", "title": "What I do", "enabled": True},
            "skills": {"label": "Skills", "title": "Stack", "enabled": True},
            "projects": {"label": "Work", "title": "Projects", "enabled": True},
            "experience": {"label": "Path", "title": "Experience", "enabled": True},
            "contact": {"label": "Contact", "title": "Say hello", "enabled": True},
        },
        "settings": DEFAULT_SETTINGS,
        "about": [
            {"id": "a1", "title": "Web", "desc": "Fast, responsive interfaces.", "visible": True},
            {"id": "a2", "title": "AI", "desc": "Smart tools that solve problems.", "visible": True},
            {"id": "a3", "title": "Automation", "desc": "Less manual work, more output.", "visible": True},
        ],
        "skills": [
            {"id": "s1", "name": "HTML / CSS", "level": 95, "visible": True},
            {"id": "s2", "name": "JavaScript", "level": 80, "visible": True},
            {"id": "s3", "name": "Python", "level": 92, "visible": True},
        ],
        "skill_tags": [
            {"id": "t1", "name": "Git", "visible": True},
            {"id": "t2", "name": "Flask", "visible": True},
        ],
        "projects": [],
        "experience": [],
    }
    migrated = False
    for key, val in defaults.items():
        if key not in content:
            content[key] = val
            migrated = True

    old_settings = json.dumps(content.get("settings", {}), sort_keys=True)
    content["settings"] = deep_merge(DEFAULT_SETTINGS, content.get("settings", {}))
    if json.dumps(content["settings"], sort_keys=True) != old_settings:
        migrated = True

    for sec_key, sec_default in defaults["sections"].items():
        sec = content.setdefault("sections", {}).setdefault(sec_key, {})
        for field, field_val in sec_default.items():
            if field not in sec:
                sec[field] = field_val
                migrated = True

    for item in content.get("about", []):
        if "id" not in item:
            item["id"] = secrets.token_hex(6)
            migrated = True
        if "visible" not in item:
            item["visible"] = True
            migrated = True
    for item in content.get("skills", []):
        if "id" not in item:
            item["id"] = secrets.token_hex(6)
            migrated = True
        if "visible" not in item:
            item["visible"] = True
            migrated = True
    for item in content.get("skill_tags", []):
        if isinstance(item, str):
            migrated = True
        elif "id" not in item:
            item["id"] = secrets.token_hex(6)
            migrated = True
        if isinstance(item, dict) and "visible" not in item:
            item["visible"] = True
            migrated = True
    if any(isinstance(t, str) for t in content.get("skill_tags", [])):
        content["skill_tags"] = [
            {"id": secrets.token_hex(6), "name": t, "visible": True} if isinstance(t, str) else t
            for t in content["skill_tags"]
        ]
        migrated = True
    for item in content.get("experience", []):
        if "id" not in item:
            item["id"] = secrets.token_hex(6)
            migrated = True
        if "visible" not in item:
            item["visible"] = True
            migrated = True
    for item in content.get("projects", []):
        if "id" not in item:
            item["id"] = secrets.token_hex(6)
            migrated = True
        if "visible" not in item:
            item["visible"] = True
            migrated = True

    if migrated:
        save_site_content(content)
    return content


COLLECTIONS = {
    "about": {
        "key": "about",
        "required": ("title", "desc"),
        "fields": ("title", "desc", "visible"),
        "defaults": {"visible": True},
    },
    "skills": {
        "key": "skills",
        "required": ("name",),
        "fields": ("name", "level", "visible"),
        "defaults": {"level": 80, "visible": True},
    },
    "skill_tags": {
        "key": "skill_tags",
        "required": ("name",),
        "fields": ("name", "visible"),
        "defaults": {"visible": True},
    },
    "experience": {
        "key": "experience",
        "required": ("role", "desc"),
        "fields": ("year", "role", "company", "desc", "visible"),
        "defaults": {"year": "", "company": "", "visible": True},
    },
}


def find_in_collection(content, collection_key, item_id):
    items = content.get(collection_key, [])
    return next((i for i, x in enumerate(items) if x.get("id") == item_id), None)


def save_site_content(content):
    with open(SITE_CONTENT_FILE, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=4, ensure_ascii=False)


def load_messages():
    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        messages = json.load(f)
    migrated = False
    for msg in messages:
        if "read" not in msg:
            msg["read"] = False
            migrated = True
        if "id" not in msg:
            msg["id"] = secrets.token_hex(8)
            migrated = True
        if "created_at" not in msg:
            msg["created_at"] = datetime.now(timezone.utc).isoformat()
            migrated = True
    if migrated:
        save_messages(messages)
    return messages


def save_messages(messages):
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=4)


def admin_required():
    return session.get("admin_logged_in") is True and session.get("admin_token") is not None


def login_admin(username):
    session.clear()
    session.permanent = True
    session["admin_logged_in"] = True
    session["admin_user"] = username
    session["admin_token"] = secrets.token_hex(16)
    session.modified = True


def logout_admin():
    session.clear()
    session.modified = True


def allowed_file(filename, allowed):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


@app.after_request
def secure_admin_response(response):
    if request.path.startswith("/admin") or request.path == "/admin-login":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


visitors = 0


@app.route("/")
def index():
    global visitors
    visitors += 1
    site = load_site_content()
    settings = site.get("settings", DEFAULT_SETTINGS)
    projects = visible_items(site.get("projects", []))
    site_public = dict(site)
    site_public["about"] = visible_items(site.get("about", []))
    site_public["skills"] = visible_items(site.get("skills", []))
    site_public["skill_tags"] = visible_items(site.get("skill_tags", []))
    site_public["experience"] = visible_items(site.get("experience", []))
    return render_template(
        "index.html",
        site=site_public,
        settings=settings,
        projects=projects,
        visitors=visitors,
    )


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        if verify_admin(username, password):
            login_admin(username)
            return redirect(url_for("admin"))

        return render_template("admin_login.html", error="Invalid username or password.", logged_out=False, expired=False)

    if admin_required():
        return redirect(url_for("admin"))

    logged_out = request.args.get("logged_out") == "1"
    expired = request.args.get("expired") == "1"
    return render_template("admin_login.html", error=None, logged_out=logged_out, expired=expired)


VALID_ADMIN_TABS = frozenset({
    "hero", "layout", "messages", "contact", "about", "skills", "projects", "experience",
})


@app.route("/admin")
def admin():
    if not admin_required():
        return redirect(url_for("admin_login"))

    site = load_site_content()
    messages = load_messages()
    unread_count = sum(1 for m in messages if not m.get("read"))
    tab = request.args.get("tab", "hero")
    if tab not in VALID_ADMIN_TABS:
        tab = "hero"

    return render_template(
        "admin.html",
        messages=messages,
        unread_count=unread_count,
        admin_username=load_admin_credentials()[0],
        site=site,
        projects=site.get("projects", []),
        about_items=site.get("about", []),
        skills=site.get("skills", []),
        skill_tags=site.get("skill_tags", []),
        experience=site.get("experience", []),
        tab=tab,
    )


@app.route("/admin-logout", methods=["GET", "POST"])
def admin_logout():
    logout_admin()
    response = redirect(url_for("admin_login", logged_out=1))
    response.delete_cookie(app.config.get("SESSION_COOKIE_NAME", "session"))
    return response


@app.route("/admin/api/site", methods=["POST"])
def update_site():
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    content = load_site_content()

    profile = content.setdefault("profile", {})
    contact = content.setdefault("contact", {})

    for key in ("name", "title", "hero_title", "hero_subtitle", "location", "location_full", "avatar", "github_user"):
        if key in data:
            profile[key] = (data[key] or "").strip()

    for key in ("email", "whatsapp", "github", "cv_url"):
        if key in data:
            contact[key] = (data[key] or "").strip()

    # normalize whatsapp — digits only
    if contact.get("whatsapp"):
        contact["whatsapp"] = "".join(c for c in contact["whatsapp"] if c.isdigit())

    save_site_content(content)
    return jsonify({"status": "success", "message": "Site info updated! Refresh the portfolio to see changes."})


@app.route("/admin/api/settings", methods=["POST"])
def update_settings():
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    content = load_site_content()
    content["settings"] = deep_merge(content.get("settings", DEFAULT_SETTINGS), data)
    save_site_content(content)
    return jsonify({"status": "success", "message": "Layout settings saved!", "settings": content["settings"]})


@app.route("/admin/api/toggle/<collection>/<item_id>", methods=["PATCH"])
def toggle_collection_item(collection, item_id):
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    if collection == "projects":
        content = load_site_content()
        project = next((p for p in content.get("projects", []) if p.get("id") == item_id), None)
        if not project:
            return jsonify({"status": "error", "message": "Project not found."}), 404
        project["visible"] = not project.get("visible", True)
        save_site_content(content)
        state = "visible" if project["visible"] else "hidden"
        return jsonify({"status": "success", "message": f"Project is now {state}.", "visible": project["visible"]})

    cfg = COLLECTIONS.get(collection)
    if not cfg:
        return jsonify({"status": "error", "message": "Invalid collection."}), 400

    content = load_site_content()
    idx = find_in_collection(content, cfg["key"], item_id)
    if idx is None:
        return jsonify({"status": "error", "message": "Item not found."}), 404

    item = content[cfg["key"]][idx]
    item["visible"] = not item.get("visible", True)
    save_site_content(content)
    state = "visible" if item["visible"] else "hidden"
    return jsonify({"status": "success", "message": f"Item is now {state}.", "visible": item["visible"]})

@app.route("/admin/api/sections", methods=["POST"])
def update_sections():
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    content = load_site_content()
    sections = content.setdefault("sections", {})

    for section_key in ("about", "skills", "projects", "experience", "contact"):
        if section_key in data and isinstance(data[section_key], dict):
            sec = sections.setdefault(section_key, {})
            if "label" in data[section_key]:
                sec["label"] = (data[section_key]["label"] or "").strip()
            if "title" in data[section_key]:
                sec["title"] = (data[section_key]["title"] or "").strip()
            if "enabled" in data[section_key]:
                sec["enabled"] = bool(data[section_key]["enabled"])

    save_site_content(content)
    return jsonify({"status": "success", "message": "Section settings updated!"})


@app.route("/admin/api/<collection>", methods=["POST"])
def add_collection_item(collection):
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    cfg = COLLECTIONS.get(collection)
    if not cfg:
        return jsonify({"status": "error", "message": "Invalid collection."}), 400

    data = request.get_json() or {}
    for field in cfg["required"]:
        if not str(data.get(field, "")).strip():
            return jsonify({"status": "error", "message": f"'{field}' is required."}), 400

    content = load_site_content()
    item = {"id": secrets.token_hex(6)}
    for field in cfg["fields"]:
        if field == "level":
            item[field] = max(0, min(100, int(data.get(field, cfg["defaults"].get("level", 80)))))
        elif field == "visible":
            item[field] = bool(data.get(field, cfg["defaults"].get("visible", True)))
        else:
            item[field] = str(data.get(field, cfg["defaults"].get(field, ""))).strip()

    content.setdefault(cfg["key"], []).append(item)
    save_site_content(content)
    return jsonify({"status": "success", "message": "Item added!", "item": item})


@app.route("/admin/api/<collection>/<item_id>", methods=["PUT"])
def update_collection_item(collection, item_id):
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    cfg = COLLECTIONS.get(collection)
    if not cfg:
        return jsonify({"status": "error", "message": "Invalid collection."}), 400

    content = load_site_content()
    idx = find_in_collection(content, cfg["key"], item_id)
    if idx is None:
        return jsonify({"status": "error", "message": "Item not found."}), 404

    data = request.get_json() or {}
    item = content[cfg["key"]][idx]
    for field in cfg["fields"]:
        if field in data:
            if field == "level":
                item[field] = max(0, min(100, int(data[field])))
            elif field == "visible":
                item[field] = bool(data[field])
            else:
                item[field] = str(data[field] or "").strip()

    save_site_content(content)
    return jsonify({"status": "success", "message": "Item updated!", "item": item})


@app.route("/admin/api/<collection>/<item_id>", methods=["DELETE"])
def delete_collection_item(collection, item_id):
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    cfg = COLLECTIONS.get(collection)
    if not cfg:
        return jsonify({"status": "error", "message": "Invalid collection."}), 400

    content = load_site_content()
    items = content.get(cfg["key"], [])
    new_items = [x for x in items if x.get("id") != item_id]

    if len(new_items) == len(items):
        return jsonify({"status": "error", "message": "Item not found."}), 404

    content[cfg["key"]] = new_items
    save_site_content(content)
    return jsonify({"status": "success", "message": "Item removed."})


@app.route("/admin/api/projects", methods=["POST"])
def add_project():
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    category = (data.get("category") or "frontend").strip().lower()
    desc = (data.get("desc") or "").strip()
    details = (data.get("details") or desc).strip()

    if not title or not desc:
        return jsonify({"status": "error", "message": "Title and short description are required."}), 400

    content = load_site_content()
    project = {
        "id": secrets.token_hex(6),
        "title": title,
        "category": category,
        "desc": desc,
        "details": details,
        "img": (data.get("img") or "").strip() or "/static/images/portfolio-website.png",
        "demo_url": (data.get("demo_url") or "").strip(),
        "github_url": (data.get("github_url") or "").strip(),
        "visible": True,
    }
    content.setdefault("projects", []).append(project)
    save_site_content(content)

    return jsonify({"status": "success", "message": "Project added!", "project": project})


@app.route("/admin/api/projects/<project_id>", methods=["PUT"])
def update_project(project_id):
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    content = load_site_content()
    project = next((p for p in content.get("projects", []) if p.get("id") == project_id), None)

    if not project:
        return jsonify({"status": "error", "message": "Project not found."}), 404

    for key in ("title", "category", "desc", "details", "img", "demo_url", "github_url"):
        if key in data:
            project[key] = (data[key] or "").strip()

    if "visible" in data:
        project["visible"] = bool(data["visible"])

    save_site_content(content)
    return jsonify({"status": "success", "message": "Project updated!", "project": project})


@app.route("/admin/api/projects/<project_id>", methods=["DELETE"])
def remove_project(project_id):
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    content = load_site_content()
    projects = content.get("projects", [])
    new_list = [p for p in projects if p.get("id") != project_id]

    if len(new_list) == len(projects):
        return jsonify({"status": "error", "message": "Project not found."}), 404

    content["projects"] = new_list
    save_site_content(content)
    return jsonify({"status": "success", "message": "Project removed from portfolio."})


@app.route("/admin/api/upload", methods=["POST"])
def upload_file():
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    upload_type = (request.form.get("type") or "image").strip().lower()
    file = request.files.get("file")

    if not file or not file.filename:
        return jsonify({"status": "error", "message": "No file selected."}), 400

    if upload_type == "cv":
        if not allowed_file(file.filename, ALLOWED_CV_EXT):
            return jsonify({"status": "error", "message": "CV must be a PDF file."}), 400
        filename = "cv.pdf"
        path = os.path.join(CV_DIR, filename)
        file.save(path)
        url = f"/static/uploads/{filename}"
    elif upload_type == "avatar":
        if not allowed_file(file.filename, ALLOWED_IMAGE_EXT):
            return jsonify({"status": "error", "message": "Avatar must be PNG, JPG, or WEBP."}), 400
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"avatar.{ext}"
        path = os.path.join("static", "images", filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file.save(path)
        url = f"/static/images/{filename}"
    else:
        if not allowed_file(file.filename, ALLOWED_IMAGE_EXT):
            return jsonify({"status": "error", "message": "Image must be PNG, JPG, or WEBP."}), 400
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{secrets.token_hex(8)}.{ext}"
        path = os.path.join(PROJECT_IMG_DIR, filename)
        file.save(path)
        url = f"/static/uploads/projects/{filename}"

    if upload_type == "cv":
        content = load_site_content()
        content.setdefault("contact", {})["cv_url"] = url
        save_site_content(content)
    elif upload_type == "avatar":
        content = load_site_content()
        content.setdefault("profile", {})["avatar"] = url
        save_site_content(content)

    return jsonify({"status": "success", "message": "File uploaded!", "url": url})


@app.route("/send-message", methods=["POST"])
def send_message():
    data = request.get_json() or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify({"status": "error", "message": "All fields are required."}), 400

    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"status": "error", "message": "Please enter a valid email address."}), 400

    all_messages = load_messages()
    all_messages.append({
        "id": secrets.token_hex(8),
        "name": name,
        "email": email,
        "message": message,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    save_messages(all_messages)

    return jsonify({"status": "success", "message": "Message sent successfully!"})


@app.route("/api/messages")
def get_messages():
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    return jsonify(load_messages())


@app.route("/delete-message/<message_id>", methods=["DELETE"])
def delete_message(message_id):
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    messages = load_messages()
    index = next((i for i, m in enumerate(messages) if m.get("id") == message_id), None)

    if index is None:
        return jsonify({"status": "error", "message": "Message not found."}), 404

    messages.pop(index)
    save_messages(messages)

    return jsonify({"status": "success", "message": "Message deleted successfully."})


@app.route("/toggle-read/<message_id>", methods=["PATCH"])
def toggle_read(message_id):
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    messages = load_messages()
    msg = next((m for m in messages if m.get("id") == message_id), None)

    if msg is None:
        return jsonify({"status": "error", "message": "Message not found."}), 404

    msg["read"] = not msg.get("read", False)
    save_messages(messages)

    return jsonify({
        "status": "success",
        "read": msg["read"],
        "message": "Message marked as read." if msg["read"] else "Message marked as unread.",
    })


@app.route("/admin/change-credentials", methods=["POST"])
def change_credentials():
    if not admin_required():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    current_password = (data.get("current_password") or "").strip()
    new_username = (data.get("new_username") or "").strip()
    new_password = (data.get("new_password") or "").strip()

    _, admin_pass = load_admin_credentials()

    if current_password != admin_pass:
        return jsonify({"status": "error", "message": "Current password is incorrect."}), 400

    if not new_username or not new_password:
        return jsonify({"status": "error", "message": "New username and password are required."}), 400

    if len(new_password) < 6:
        return jsonify({"status": "error", "message": "Password must be at least 6 characters."}), 400

    save_admin_credentials(new_username, new_password)

    return jsonify({"status": "success", "message": "Credentials updated successfully."})


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "true").lower() == "true", host="0.0.0.0", port=5000)
