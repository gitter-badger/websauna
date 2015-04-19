import sys

from pyramid.security import Allow
from pyramid_web20.system import crud
from pyramid_web20.system.crud import sqlalchemy as sqlalchemy_crud
from pyramid_web20.system.crud.sqlalchemy import ModelCRUD
from pyramid_web20.utils import traverse



class Root:
    __name__ = ""


class Admin:
    """Admin interface main object.

    We know what panels are registered on the main admin screen.
    """

    # Root defines where admin interaface lies in the URL space
    __parent__ = Root()
    __name__ = "admin"

    __acl__ = [
        (Allow, 'group:admin', 'view'),
    ]

    def __init__(self):
        self.model_admins = {}

    @classmethod
    def get_admin(cls, registry):
        """Get hold of admin singleton."""
        return registry.settings["pyramid_web20.admin"]

    def get_panels(self):
        for model_admin in self.model_admins.values():
            if model_admin.panel:
                yield model_admin.panel

    def scan(self, config, module):
        """Picks up admin definitions from the module."""

        __admin__ = getattr(module, "__admin__", None)

        if not __admin__:
            raise RuntimeError("Admin tried to scan module {}, but it doesn't have __admin__ attribute. The module probably doesn't define any admin objects.".format(module))

        for model_dotted, admin_cls in __admin__.items():

            # Instiate model admin
            try:
                model = config.maybe_dotted(model_dotted)
            except ImportError as e:
                raise ImportError("Tried to initialize model admin for {}, but could not import it".format(model_dotted)) from e

            try:
                model_admin = admin_cls(model)
            except Exception as e:
                raise RuntimeError("Could not instiate model admin {} for model {}".format(admin_cls, model)) from e

            id = getattr(model_admin, "id", None)
            if not id:
                raise RuntimeError("Model admin does not define id {}".format(model_admin))

            # Keep ACL chain intact
            traverse.make_lineage(self, model_admin, id)

            self.model_admins[id] = model_admin

    def __getitem__(self, name):

        # Traverse to models
        model_admin = self.model_admins[name]
        return model_admin


class ModelAdmin:
    """Present one model in admin interface."""

    #: URL traversing id
    id = None

    #: Admin panel instance used on the admin homepage
    panel = None

    #: CRUD instance used to render model listing, view, add, edit, delete, etc.
    crud = None

    def __init__(self, model):
        self.model = model
        self.init_lineage()

    def init_lineage(self):
        """Make sure that all context objects have parent pointers set."""
        traverse.make_lineage(self, self.panel, "panel")
        traverse.make_lineage(self, self.crud, "crud")

    @classmethod
    def register(cls, model):
        """Mark the class to become a model admin on Admin.scan()."""

        def inner(wrapped_cls):

            assert cls.__module__, "Class without module attached cannot possibly work"

            # XXX: Now store registered model admins in a module attribute, which will be later picked up scan(). Think some smarter way to do this, like using events and pyramid config registry.
            module = sys.modules[wrapped_cls.__module__]
            __admin__ = getattr(module, "__admin__", {})
            __admin__[model] = wrapped_cls
            module.__admin__ = __admin__

            return wrapped_cls

        return inner

    def __getitem__(self, name):
        if name == "panel":
            return self.panel

        if name == "crud":
            return self.crud

        return None

class AdminPanel:

    #: Template hint which template to use for this panel
    template = "admin/model_panel.html"

    def __init__(self, title):
        self.title = title

    def get_model(self):
        model_admin = self.__parent__
        return model_admin.model



class Listing(sqlalchemy_crud.Listing):
    template = "admin/listing.html"
    base_template = "admin/base.html"



def admin_root_factory(request):
    """Get the admin object for the routes."""
    admin = Admin.get_admin(request.registry)
    return admin



