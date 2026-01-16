from flask import Flask, render_template
from jinja2 import ChoiceLoader, FileSystemLoader

from common.utils import get_tabs, get_side_tabs
import common.config as mod_cfg

app = Flask(__name__)

# Register blueprints
from modules.calendar.routes import calendar_bp
from modules.notes.routes import notes_bp
from modules.tasks.tasks import tasks_bp

app.register_blueprint(calendar_bp, url_prefix="/calendar")
app.register_blueprint(notes_bp, url_prefix="/notes")
app.register_blueprint(tasks_bp, url_prefix="/tasks")

@app.route('/')
def index():
    return render_template(
        'layout.html',
        active_tab='notes',
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title='Home',
        content_html='<p>Welcome to LifePIM!</p>'
    )

if __name__ == "__main__":
    app.run(debug=True)

"""
# Auto-register all modules as blueprints
for _, modname, _ in pkgutil.iter_modules(['modules']):
    module = importlib.import_module(f'modules.{modname}.views')
    if hasattr(module, 'bp'):
        app.register_blueprint(module.bp, url_prefix=f'/{modname}')

        

SIDE_TABS = [
 { 'icon': '*', 'id': 'any', 'label': 'All Projects'},
 { 'icon': '🔒', 'id': 'pers', 'label': 'Personal'},
 { 'icon': '💊', 'id': 'health', 'label': 'Health'},
 { 'icon': '👪', 'id': 'family', 'label': 'Family'},
 { 'icon': '🏈', 'id': 'sport', 'label': 'Sport'},
 { 'icon': '🏚️', 'id': 'house', 'label': 'House'},
 { 'icon': '🍕', 'id': 'food', 'label': 'Food'},
 { 'icon': '🚗', 'id': 'car', 'label': 'Car'},
 { 'icon': '🎉', 'id': 'fun', 'label': 'Fun'},
 { 'icon': '🕹️', 'id': 'games', 'label': 'Games'},
 { 'icon': '🖥️', 'id': 'dev', 'label': 'Dev'},
 { 'icon': '🖥️', 'id': 'dev/UE5', 'label': 'UE5'},
 { 'icon': '🖥️', 'id': 'dev/Python', 'label': 'Python'},
 { 'icon': '📐', 'id': 'design', 'label': 'Design'},
 { 'icon': '📐', 'id': 'design/write', 'label': 'Writing'},
 { 'icon': '📐', 'id': 'design/programs', 'label': 'Program Design'},
 { 'icon': '📻', 'id': 'make', 'label': 'Make'},
 { 'icon': '📻', 'id': 'make/rasbpi', 'label': 'RasbPI'},
 { 'icon': '📻', 'id': 'make/pc', 'label': 'PC'},
 { 'icon': '💼', 'id': 'work', 'label': 'Work'},
 { 'icon': '💼', 'id': 'work/business', 'label': 'Business'},
 { 'icon': '💼', 'id': 'work/side', 'label': 'Side Gigs'},
 { 'icon': '👩🏻‍🎓', 'id': 'learn', 'label': 'Learn'},
 { 'icon': '🕵', 'id': 'ai', 'label': 'AI'},
 { 'icon': '🧰', 'id': 'support', 'label': 'Support'},
]

TABS = [
 { 'icon': '🏠', 'id': 'home', 'label': 'Overview', 'desc': 'Overview Dashboard'},
 { 'icon': '📝', 'id': 'notes', 'label': 'Notes', 'desc': 'Notes'},
 { 'icon': '🕐', 'id': 'calendar', 'label': 'Cal', 'desc': 'Calendar, Appointments, Events, Reminders (WHEN)'},
 { 'icon': '📝', 'id': 'tasks', 'label': 'Tasks', 'desc': 'Tasks (actual list of things to do)'},
 { 'icon': '🗄️', 'id': 'data', 'label': 'Data', 'desc': 'Data' },
 { 'icon': '🎮', 'id': 'apps', 'label': 'Apps', 'desc': 'Apps'},
 { 'icon': '📂', 'id': 'files', 'label': 'Files', 'desc': 'Files'},
 { 'icon': '💿', 'id': 'media', 'label': 'Media', 'desc': 'Images, Audio, Video'},
 { 'icon': '🧱', 'id': '3d', 'label': '3D', 'desc': 'Objects / 3D / Things'},
 { 'icon': '👤', 'id': 'contacts', 'label': 'People', 'desc': 'Contacts (WHO)'},
 { 'icon': '🌏', 'id': 'places', 'label': 'Places', 'desc': 'Places (WHERE - real life, URL or virt location)'},
 { 'icon': '💲', 'id': 'money', 'label': 'Money', 'desc': 'Money'},
 { 'icon': '💻', 'id': 'etl', 'label': 'ETL', 'desc': 'ETL'},
]
        
 """
