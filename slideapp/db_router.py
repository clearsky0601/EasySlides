class SlideAppRouter:
    """Route slide content models to the switchable slides database."""

    route_app_labels = {'slideapp'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'slides'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'slides'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if (
            obj1._meta.app_label in self.route_app_labels
            or obj2._meta.app_label in self.route_app_labels
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # slideapp 的表只迁移到 slides 库，其余 app 只迁移到 default，
        # 避免同一套表在两个 alias 各落一份
        if app_label in self.route_app_labels:
            return db == 'slides'
        return db == 'default'
