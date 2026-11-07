"""HTTP CLI'nin geç yüklenen MCP modülü için resmi Superset post_init kancası."""

from superset.initialization import SupersetAppInitializer

from flyup3 import mcp_branding


class FlyUp3AppInitializer(SupersetAppInitializer):
    def post_init(self):
        super().post_init()
        # Flask mutator HTTP CLI'de core MCP dependency injection'dan önce çalışır.
        # apply, modül yoksa bir şey kaydetmez; stdio'da ikinci çağrı zararsızdır.
        mcp_branding.apply(self.superset_app)
