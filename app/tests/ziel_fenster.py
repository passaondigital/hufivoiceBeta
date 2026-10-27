import gi; gi.require_version("Gtk","3.0")
from gi.repository import Gtk, GLib
w=Gtk.Window(title="Zielfenster"); w.set_default_size(600,200)
tv=Gtk.TextView(); w.add(tv); w.show_all(); w.present()
def sichern():
    b=tv.get_buffer(); open("/tmp/ziel.txt","w").write(b.get_text(b.get_start_iter(),b.get_end_iter(),True)); return True
GLib.timeout_add(300,sichern); w.connect("destroy",Gtk.main_quit); Gtk.main()
