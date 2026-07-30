from flask import Blueprint, render_template, request


icons_bp = Blueprint("icons", __name__, template_folder="templates")


@icons_bp.route("/picker")
def picker_route():
    return render_template(
        "icon_picker.html",
        target=request.args.get("target", ""),
        mode=request.args.get("mode", "replace"),
    )
