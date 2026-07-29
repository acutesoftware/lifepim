# Notes on UI Layout and Configuration
The idea of LifePIM is to have the menus completely data driven.

## Tab Interface

A tabbed interface should allow users to get to most personal information in 2 clicks.

 - Top tab = Type of Information - Notes, Tasks, Calendar, Contacts, Files, Videos, etc
 - Side tab = Area of Information - this is your areas, grouped logically into sub groups


### Top Tabs



### Side Tabs



## Linking UI to actions / tables

## UI Linked to actions / API routes
TODO - make sure every single CSV file and database table can be mapped to a submenu/area

### UI Linked to Commands
TODO - make sure the following common tasks are available in the appropriate places
The list below needs to be accessibly, and ideally prominent when user selects appropriate combo of Areas and Tabs.

```
    Car - last serviced, Rego due, tax due, insurance due, fuel log
    Health - weight, BMI, blood pressure, medications, allergies, conditions, doctors, dentist
    Home - insurance, mortgage, rent, council tax, utilities, repairs, improvements
    Games - collection, wish list, completed
    Work - areas, tasks, meetings, contacts
    Shopping - Food Shopping, Wish List, To Buy, Receipts
    Family - birthdays, events, contacts, medical info
    Food - recipes, meal plans, shopping lists
    Admin - passwords, licenses, warranties, manuals
    Pers - diary, journal, photos, videos, events, contacts
    Study - courses, notes, tasks, calendar, contacts
    Design - areas, ideas, inspiration, contacts
    Fun - books, movies, music, games, hobbies
    Web - bookmarks, passwords, ideas, areas, contacts
    Business - clients, areas, tasks, invoices, contacts
    Dev - areas, tasks, bugs, ideas, contacts
    RasbPI - areas, tasks, ideas, contacts
    Support - warranties, manuals, contacts, tasks
    AI - areas, tasks, ideas, contacts
    Area - name, description, start date, end date, status, priority, tags, notes, tasks, calendar events, files, images, links

    From the above list, we need to implement the following database tables:
    - areas
    - tasks
    - calendar_events
    - notes
    - files
    - images
    - contacts
    - tags
    - links
    - passwords
    - reminders
    - locations
    - budgets
    - expenses
    - incomes
    - music
    - videos
    - badges
    - checklists
    - databases
    - spreadsheets
    - recipes
    - shopping_lists
    - fuel_logs
    - medical_info
    - service_records
    - warranties
    - licenses  
    - manuals
    - bookmarks
    - journals
    - logs
    - meetings
    - appointments

```



## Appendix

### Scratchpad, ideas for icons

```
    toolbar_definition_OLD =  [  # [icon, name, function, comments]
    ['🏠', 'home',     'tb_home',         '🏠📰 This is the overview page'],
    ['🕐', 'calendar', 'tb_calendar', '⌚📅 🕐 Area overview showing current list of tasks being worked on'],
    ['☑',  'tasks',    'tb_tasks',    '☑✔📎🔨✘☑ ⛏ ☹     💻 💹 Tasks'],
    ['📝', 'notes',    'tb_notes',    '🗒✎📝 ✏ 🗊Team wiki page - ultra simple'], #
    ['👤', 'contacts', 'tb_contacts',     '☎👱  👤  Contacts view'],
    ['🌏️', 'places',   'tb_places',    '🌏🛰️⛟ ⌖ ⛰    💻 💹Locations - maps, people finder'],
    ['▦',  'data',     'tb_data',    '▧🗒 🗊data tables'],
    ['🏆', 'badges',   'tb_badges',     '★ ⛤ ✵ ✭ ⚜'],
    ['💲', 'money',    'tb_money',      ''],
    ['♬',  'music',    'tb_music',     '🗒 🗊music'],
    ['🖼',  'images',  'tb_images',      '🗒 🗊images'],
    ['🎮', 'apps',     'tb_apps',     '👍 👎 '],
    ['📂',  'files',   'tb_files',     '🗒 🗊images and files'],
    ['⚿',  'admin',   'tb_admin',      'passwords'],
    ['⚙',  'options', 'tb_options',     'Options for LifePIM'],
    ['⚙',  'about',   'tb_about',    'About LifePIM']
    ]


    """other icons on top to include - or possibly sub top menus
    food🍕
    break ☕  movie ticket 
    moon phases to show : 🌑🌒🌓🌔🌕🌖🌗🌘
    notes : ideas 💡, lists 📇   others : 📑📒📓📔📕📖📗📘📙📚 🖋️

    notes : shitlist 💩 
    money : 💵 💳

    comms : 📧📨✉️ 📨 📩 📤 📥 📦 📫 📪 📨 📬 📭  🗳️ 📞📟 📠 
    news: 📡 📢
    tasks: ✅ ✔️ ✖️ ❌ ❎  ☑️ blueprint = 📘
    package : 📦  💼  💽 💾  (??)
    3d objects / things : 📦 🏷️ 🎁 🎀 🏵️ 🔳 🏺 👀  🔌 🧱 🏷
    music : 🎵 🎶 🎼 🎤 🎧 🥁 🎷 🎸 🎹 📻 📱
    images : 🖼️ 🖌️ 🎨 📷 📸 
    video : 📹 🎥 📽️ 🎞️

    design / cad - 📐
    tools : 🔦 🔧  🔨 🔩

    links : 🔗  🖇️  📎  🧷  🗜️  ⚖️  🪝  🪜  🧰  🧲  🪃  🪁  🛠️  🛡️  🗡️  ⚔️  🔫  💣  🪓

    ai: 🕵
    fun : 🕺

    staff / groups : 👥 
    family : 👪


    health : ⚕️  🏥  💊  🩺  🦠  🧬  🦷  🦴  🧠  ❤️‍🩹 ❤️‍🔥 ❤️ 💔 💓 💗 💖 💘 💝

    AREA ICONS
    garden : 🌳 🌲 🌴 🌵 🌾 🌿 ☘️ 🍀 🎍 🎋 🍃 🍂 🍁 🌱
    house : 🏠🏡🏘️🏚️🏢🏣🏤🏥🏦🏨
    car : 🚗🚕🚙🚌🚎🏎️🚓🚑🚒🚐🚚🚛🚜🛺
    health : 🏥💊🩺🦷🦴🧠❤️‍🩹❤️‍🔥❤️💔💓💗💖💘💝
    games : 🎮 🕹️🎲 🎯 🧩 🎭 🎰 🃏 🎴 ♠️ ♥️ ♦️ ♣️ 🀄 🏆
    travel : ✈️🚢🧳🚀🗺️👣🌍🌎🌏🌐 🗾 🧭 🏔️ ⛰️ 🌋  🗻 🏕️ 🏖️

    study : 📖 📚 📕 📗 📘 📙 📔 📒 📓 📑 🧾 📜 📰
    work : 💼 📁 📂 🗂️ 🗃️ 🗄️ 📅 📆 📇 📈 📉 📊 📋 📌 📍 ✂️ 🖊️ 🖋️ ✒️ 🖌️ 🖍️ 📝
    admin : 🗝️ 🔐 🔒 🔓 🛂 
    make: 🛠️ 🧰 🔧 🔨 ⚙️ 🪛 🪚 🪜
    etl :  🔣  (data extract, transform, load)
    dev: 💻 🖥️ 🖱️ ⌨️ 🖨️ 🖲️ 💾 💿 📀
    develop : 🧑‍💻 👨‍💻 👩‍💻 🧑‍🔧 👨‍🔧 👩‍🔧 🧑‍🏭 👨‍🏭 👩‍🏭
    code :  </>  {}  []  ()
    sports: ⚽ 🏀 🏈 ⚾ 🥎 🎾 🏐 🏉 🎱 🪀 🪁 🏓 🏸 🥅 🏒 🏑 🥍 🏏 ⛳ 🏹 🎣 🤿 🛶 🚣‍♂️ 🏊‍♂️ 🤽‍♂️ 🚴‍♂️ 🚵‍♂️ 🏋️‍♂️ 🤸‍♂️ 🤼‍♂️ 🤺 🤾‍♂️
    fun : 🎉 🎊 🎈 🎂 🎁 🎀 🎆 🎇 ✨ 🎃 🎄 🎋 🎍 🏮 🎎 🎏 🎐 🧨
    cooking / food : 🥣🍳🍔🍏🍎🍐🍊🍋🍌🍉🍇🍓🫐🍈🍒🍑🥭🍍🥥🥝🍅🫒🥑🍆🥔🥕🌽🌶️🫑🥒🥬🥦🧄🧅🍄🥜🌰🍞🥐🥖🫓🥨🥯🥞🧇🧀🍖🍗🥩🥓🍔🍟🌭🍕🫔🥪🌮🌯🫕🥗🥘🫙🍝🍜🍲🍛🦪🍣🍱🥟🦀🦞🦐🦑🍤🥠🥡🧆🍦🍧🍨🍩🎂🍰🧁🥧🍪🍫🍬🍭☕🫖🍵🥤🧃🧉🍶🍺🍻🥂🍷🥃

```


