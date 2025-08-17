from Xlib import X, display, Xutil, error, XK, Xcursorfont
import subprocess
import sys
import logging
import os
import json
import traceback

app_name = "simplepywm"

user = os.getenv("USER")
path = f"/home/{user}/.config/{app_name}"
if(not os.path.isdir(f"/home/{user}/.config")):
    os.mkdir(f"/home/{user}/.config")
if(not os.path.isdir(path)):
    os.mkdir(path)

log_file = os.path.expanduser(f"{path}/{app_name}.log")
logging.basicConfig(
    filename=log_file,
    filemode='w',
    format='[%(asctime)s] %(levelname)s: %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger("SimplePyWM")

default_config = {
    "display": {
        "window": {
            "frame": {
                "border_width": 10,
                "active_background_color": "green",
                "passive_background_color": "lightblue"
            },
            "taskbar": {
                "height": 30,
                "button_border_width": 2,
                "background_color": "lightblue",
                "button_active_background_color": "white",
                "button_active_font_color": "black",
                "button_passive_background_color": "black",
                "button_passive_font_color": "green"
            },
            "minimize": {
                "color": "#FFBD44"
            },
            "maximize": {
                "color": "#00CA4E"
            },
            "close": {
                "color": "#FF605C"
            }
        }
    },
    "commands": {
        "terminal": ["kitty"],
        "filemanager": ["kitty", "lf"],
        "launcher": ["dmenu_run"]
    }
}

if("config.json" not in os.listdir(path)):
    with open(f"{path}/config.json", "w") as file:
        file.write(json.dumps(default_config, indent=4))

config = json.load(open(os.path.expanduser(f"{path}/config.json"), "r"))

class SimplePyWM:
    def __init__(self):
        self.d = display.Display()
        self.screen = self.d.screen()
        self.root = self.screen.root
        self.clients = {}
        self.frame_window_buttons = {}
        self.frame_to_button_mapping = {}
        self.old_x_y_width_height = {}
        self.dragging = False
        self.drag_start_pos = (0, 0)
        self.drag_window = None
        self.resizing = False
        self.resize_window = None
        self.resize_start_geom = None
        self.resize_start_pos = (0, 0)
        self.resize_mode = None
        self.active_frame = None
        self.frame_border_width = config["display"]["window"]["frame"]["border_width"]
        self.button_border_width = config["display"]["window"]["taskbar"]["button_border_width"]

        self.colormap = self.screen.default_colormap

        font = self.d.open_font("cursor")
        
        self.cursor_horiz = font.create_glyph_cursor(
            font,
            Xcursorfont.sb_h_double_arrow,
            Xcursorfont.sb_h_double_arrow + 1,
            (65535, 65535, 65535),
            (0, 0, 0)
        )

        self.cursor_vert = font.create_glyph_cursor(
            font,
            Xcursorfont.sb_v_double_arrow,
            Xcursorfont.sb_v_double_arrow + 1,
            (65535, 65535, 65535),
            (0, 0, 0)
        )

        self.cursor_diag = font.create_glyph_cursor(
            font,
            Xcursorfont.bottom_right_corner,
            Xcursorfont.bottom_right_corner + 1,
            (65535, 65535, 65535),
            (0, 0, 0)
        )

        self.cursor_default = font.create_glyph_cursor(
            font,
            Xcursorfont.left_ptr,
            Xcursorfont.left_ptr + 1,
            (65535, 65535, 65535),
            (0, 0, 0)
        )
        self.screen.root.change_attributes(cursor=self.cursor_default)

        try:
            self.root.change_attributes(event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.grab_shortcut()
        except error.BadAccess:
            logger.info("Another window manager is already running.")
            sys.exit(1)

        logger.info("Window manager started. Listening for window events...")

        self.taskbar_height = config["display"]["window"]["taskbar"]["height"]
        self.taskbar = self.screen.root.create_window(
            x=0,
            y=self.screen.height_in_pixels - self.taskbar_height,
            width=self.screen.width_in_pixels,
            height=self.taskbar_height,
            border_width=0,
            depth=self.screen.root_depth,
            class_=X.InputOutput,
            visual=X.CopyFromParent,
            background_pixel=self.colormap.alloc_named_color(config["display"]["window"]["taskbar"]["background_color"]).pixel,
            event_mask=X.ExposureMask | X.ButtonPressMask
        )
        self.taskbar.map()

        self.active_background_color = self.colormap.alloc_named_color(config["display"]["window"]["frame"]["active_background_color"]).pixel
        self.passive_background_color = self.colormap.alloc_named_color(config["display"]["window"]["frame"]["passive_background_color"]).pixel

        self.button_active_background_color = self.taskbar.create_gc(foreground=self.colormap.alloc_named_color(config["display"]["window"]["taskbar"]["button_active_background_color"]).pixel)
        self.button_active_font_color = self.taskbar.create_gc(foreground=self.colormap.alloc_named_color(config["display"]["window"]["taskbar"]["button_active_font_color"]).pixel)
        self.button_passive_background_color = self.taskbar.create_gc(foreground=self.colormap.alloc_named_color(config["display"]["window"]["taskbar"]["button_passive_background_color"]).pixel)
        self.button_passive_font_color = self.taskbar.create_gc(foreground=self.colormap.alloc_named_color(config["display"]["window"]["taskbar"]["button_passive_font_color"]).pixel)

        self.taskbar_buttons = []
        self.draw_taskbar()

    def set_frame_window_buttons(self, frame_id):
        win = self.clients[frame_id]
        geom = win.get_geometry()
        frame_width = geom.width + 2 * self.frame_border_width
        
        for index in range(3):
            self.frame_to_button_mapping[self.clients[win.id].id][index].configure(
                x = frame_width - ((index+2)*self.frame_border_width),
                y = 0
            )

    def maximize_window(self, win):
        frame = self.clients.get(win.id)
        if not frame:
            return

        screen_width = self.screen.width_in_pixels
        screen_height = self.screen.height_in_pixels
        border = self.frame_border_width

        geom = frame.get_geometry()
        geom_win = win.get_geometry()
        if((geom.width == screen_width) and (geom.height == screen_height - self.taskbar_height)):
            if(frame.id not in self.old_x_y_width_height):
                frame.configure(
                    x=0, y=0
                )
                return
            frame.configure(
                x=self.old_x_y_width_height[frame.id][0],
                y=self.old_x_y_width_height[frame.id][1],
                width=self.old_x_y_width_height[frame.id][2],
                height=self.old_x_y_width_height[frame.id][3]
            )
            win.configure(
                x=self.old_x_y_width_height[win.id][0],
                y=self.old_x_y_width_height[win.id][1],
                width=self.old_x_y_width_height[win.id][2],
                height=self.old_x_y_width_height[win.id][3]
            )
            self.set_frame_window_buttons(frame.id)
            return

        self.old_x_y_width_height[frame.id] = (geom.x, geom.y, geom.width, geom.height)
        self.old_x_y_width_height[win.id] = (geom_win.x, geom_win.y, geom_win.width, geom_win.height)

        frame.configure(
            x=0,
            y=0,
            width=screen_width,
            height=screen_height - self.taskbar_height
        )
        win.configure(
            x=border,
            y=border,
            width=screen_width - 2 * border,
            height=screen_height - 2 * border - self.taskbar_height
        )

        self.set_frame_window_buttons(frame.id)


    def get_window_title(self, win):
        try:
            win_obj = self.d.create_resource_object('window', win)
            wm_class = win_obj.get_wm_class()
            if wm_class and len(wm_class) > 1:
                return wm_class[1]
            elif wm_class:
                return wm_class[0]
            else:
                return "Unknown"
        except Exception as e:
            logger.warning(f"Failed to get WM_CLASS for window {win}: {e}")
            return "Unknown"

    def draw_taskbar(self):

        width = self.screen.width_in_pixels
        n = len(self.clients)
        if n == 0:
            return
        if int(n/2) == 0:
            return

        btn_width = width // int((n/2))

        counter = 0
        for i, (client_id, frame) in enumerate(self.clients.items()):
            win_title = self.get_window_title(client_id)
            if(win_title == "Unknown"):
                continue
            x = counter * btn_width
            counter += 1

            self.taskbar_buttons.append((x, client_id))

            if(self.active_frame == frame):
                self.taskbar.fill_rectangle(self.button_active_background_color, x+self.button_border_width , self.button_border_width , btn_width - 2*self.button_border_width, self.taskbar_height - 2*self.button_border_width)
                self.taskbar.draw_text(self.button_active_font_color, x + 6, self.taskbar_height // 2 + 5, win_title[:20])
            else:
                self.taskbar.fill_rectangle(self.button_passive_background_color, x+self.button_border_width , self.button_border_width , btn_width - 2*self.button_border_width, self.taskbar_height - 2*self.button_border_width)
                self.taskbar.draw_text(self.button_passive_font_color, x + 6, self.taskbar_height // 2 + 5, win_title[:20])

    def set_active_frame(self, frame):
        if(self.taskbar == frame):
            return

        if self.active_frame and self.active_frame != frame:
            try:
                self.active_frame.change_attributes(background_pixel=self.passive_background_color)
                self.active_frame.clear_area()
            except Exception as e:
                logger.warning(f"Failed to deactivate previous frame: {e}")

        self.active_frame = frame

        try:
            frame.map()
            self.clients[frame.id].map()
            frame.change_attributes(background_pixel=self.active_background_color)
            frame.clear_area()
            frame.configure(stack_mode=X.Above)
            self.clients[frame.id].set_input_focus(X.RevertToParent, X.CurrentTime)
            logger.debug(f"Set frame {frame.id} as active and raised")
        except Exception as e:
            logger.warning(f"Failed to set active frame: {e}")
        
        self.taskbar.configure(stack_mode=X.Above)


    def grab_shortcut(self):
        key_sym = XK.string_to_keysym('T')
        key_code = self.d.keysym_to_keycode(key_sym)

        modifiers = X.ControlMask | X.ShiftMask

        self.root.grab_key(key_code, modifiers, True, X.GrabModeAsync, X.GrabModeAsync)

        for key_sym in [XK.XK_Left, XK.XK_Right, XK.XK_Up, XK.XK_Down]:
            key_code = self.d.keysym_to_keycode(key_sym)
            self.root.grab_key(key_code, X.ControlMask, True,  X.GrabModeAsync, X.GrabModeAsync)
        
        key_code = self.d.keysym_to_keycode(XK.string_to_keysym('Q'))
        self.root.grab_key(key_code, X.ControlMask, True,  X.GrabModeAsync, X.GrabModeAsync)

        key_code = self.d.keysym_to_keycode(XK.string_to_keysym('E'))
        self.root.grab_key(key_code, X.ControlMask, True,  X.GrabModeAsync, X.GrabModeAsync)

        key_code = self.d.keysym_to_keycode(XK.XK_space)
        self.root.grab_key(key_code, X.ControlMask, True,  X.GrabModeAsync, X.GrabModeAsync)

    def handle_key_press(self, event):
        key_sym = self.d.keycode_to_keysym(event.detail, 1)
        if key_sym == XK.string_to_keysym('T') and event.state & X.ControlMask and event.state & X.ShiftMask:
            subprocess.Popen(config["commands"]["terminal"])

        if event.state & X.ControlMask:
            if key_sym == XK.XK_Q:
                quit()
            if key_sym == XK.XK_E:
                subprocess.Popen(config["commands"]["filemanager"])

        key_sym = self.d.keycode_to_keysym(event.detail, 0)
        if event.state & X.ControlMask:
            if key_sym == XK.XK_space:
                subprocess.Popen(config["commands"]["launcher"])

        if not self.active_frame:
            return
        
        if event.state & X.ControlMask:
            geom = self.screen.root.get_geometry()
            screen_width = geom.width
            screen_height = geom.height

            frame_border = self.frame_border_width

            client = self.clients.get(self.active_frame.id)

            if not client:
                return
            
            if key_sym == XK.XK_Left:
                self.active_frame.configure(
                    x=0,
                    y=0,
                    width=screen_width // 2,
                    height=screen_height - self.taskbar_height
                )
                client.configure(
                    x=frame_border,
                    y=frame_border,
                    width=(screen_width // 2) - 2 * frame_border,
                    height=screen_height - 2 * frame_border - self.taskbar_height
                )

            elif key_sym == XK.XK_Right:
                self.active_frame.configure(
                    x=screen_width // 2,
                    y=0,
                    width=screen_width // 2,
                    height=screen_height - self.taskbar_height
                )
                client.configure(
                    x=frame_border,
                    y=frame_border,
                    width=(screen_width // 2) - 2 * frame_border,
                    height=screen_height - 2 * frame_border - self.taskbar_height
                )

            elif key_sym == XK.XK_Up:
                self.active_frame.configure(
                    x=0,
                    y=0,
                    width=screen_width,
                    height=screen_height // 2
                )
                client.configure(
                    x=frame_border,
                    y=frame_border,
                    width=screen_width - 2 * frame_border,
                    height=(screen_height // 2) - 2 * frame_border
                )

            elif key_sym == XK.XK_Down:
                self.active_frame.configure(
                    x=0,
                    y=screen_height // 2,
                    width=screen_width,
                    height=screen_height // 2 - self.taskbar_height
                )
                client.configure(
                    x=frame_border,
                    y=frame_border,
                    width=screen_width - 2 * frame_border,
                    height=(screen_height // 2) - 2 * frame_border - self.taskbar_height
                )
            self.set_frame_window_buttons(self.active_frame.id)

    def handle_button_press(self, event):
        if event.detail != 1:
            return

        if(event.window.id in self.frame_window_buttons):
            obj = self.frame_window_buttons.get(event.window.id)
            action, target_win = obj
            if action == "close":
                target_win.destroy()
            elif action == "maximize":
                self.maximize_window(target_win)
            elif action == "minimize":
                target_win.unmap()
            return

        win = event.window

        self.set_active_frame(win)

        geom = win.get_geometry()
        frame_width = geom.width
        frame_height = geom.height
        margin = 10

        rel_x = event.event_x
        rel_y = event.event_y

        near_bottom = rel_y >= frame_height - margin
        near_right = rel_x >= frame_width - margin

        root_x = event.root_x
        root_y = event.root_y

        if near_bottom and near_right:
            resize_mode = "both"
        elif near_bottom:
            resize_mode = "vertical"
        elif near_right:
            resize_mode = "horizontal"
        else:
            resize_mode = None

        if resize_mode:
            self.resizing = True
            self.resize_window = win
            self.resize_start_pos = (root_x, root_y)
            self.resize_start_geom = geom
            self.resize_mode = resize_mode
        else:
            self.dragging = True
            self.drag_window = win
            self.drag_start_pos = (root_x - geom.x, root_y - geom.y)

        win.grab_pointer(True,
            X.PointerMotionMask | X.ButtonReleaseMask,
            X.GrabModeAsync, X.GrabModeAsync,
            X.NONE, X.NONE, X.CurrentTime)

        if event.window.id == self.taskbar.id:
            x = event.event_x
            for btn_x, client_id in self.taskbar_buttons:
                if x >= btn_x and x < btn_x + self.screen.width_in_pixels // (len(self.clients)/2):
                    frame = self.clients[client_id]
                    self.set_active_frame(frame)
                    break
            return

    def handle_motion_notify(self, event):
        win = event.window

        if event.window.id == self.taskbar.id:
            return

        if not self.resizing and not self.dragging:
            geom = win.get_geometry()
            x, y = event.event_x, event.event_y
            margin = 10

            near_right = x >= geom.width - margin
            near_bottom = y >= geom.height - margin

            if near_right and near_bottom:
                cursor = self.cursor_diag
            elif near_right:
                cursor = self.cursor_horiz
            elif near_bottom:
                cursor = self.cursor_vert
            else:
                cursor = self.cursor_default

            win.change_attributes(cursor=cursor)
        
        if self.resizing and self.resize_window:
            frame = self.resize_window
            client = self.clients.get(frame.id)

            if not client:
                logger.warning(f"No client found for frame {frame.id}")
                return

            start_x, start_y = self.resize_start_pos
            dx = event.root_x - start_x
            dy = event.root_y - start_y

            frame_geom = self.resize_start_geom
            border = self.frame_border_width

            new_width = frame_geom.width
            new_height = frame_geom.height

            if self.resize_mode in ("horizontal", "both"):
                new_width = max(50, frame_geom.width + dx)
            if self.resize_mode in ("vertical", "both"):
                new_height = max(50, frame_geom.height + dy)


            frame.configure(width=new_width, height=new_height)

            client.configure(width=new_width - 2 * border, height=new_height - 2 * border)
            self.set_frame_window_buttons(frame.id)

        if self.dragging and self.drag_window:
            offset_x, offset_y = self.drag_start_pos
            new_x = event.root_x - offset_x
            new_y = event.root_y - offset_y
            
            self.drag_window.configure(x=new_x, y=new_y)

    def handle_button_release(self, event):
        if self.dragging:
            self.drag_window = None
            self.dragging = False

        if self.resizing:
            self.resize_window = None
            self.resizing = False
            self.resize_mode = None

        self.d.ungrab_pointer(X.CurrentTime)

    def run(self):
        while True:
            event = self.d.next_event()

            if event.type == X.MapRequest:
                self.handle_map_request(event)
                self.taskbar.clear_area()
            if event.type == X.ConfigureRequest:
                self.handle_configure_request(event)
            if event.type == X.DestroyNotify:
                self.handle_destroy_notify(event)
                self.taskbar.clear_area()
            if event.type == X.UnmapNotify:
                self.handle_unmap_notify(event)
                self.taskbar.clear_area()
            if event.type == X.KeyPress:
                self.handle_key_press(event)
            if event.type == X.ButtonPress:
                self.handle_button_press(event)
            if event.type == X.MotionNotify:
                self.handle_motion_notify(event)
            if event.type == X.ButtonRelease:
                self.handle_button_release(event)
            self.draw_taskbar()

    def handle_map_request(self, event):
        win = event.window
        win_id = win.id

        if win_id in self.clients:
            win.map()
            return


        attrs = win.get_attributes()
        geom = win.get_geometry()

        border_width = self.frame_border_width
        frame = self.root.create_window(
            geom.x, geom.y,
            geom.width + 2 * border_width,
            geom.height + 2 * border_width,
            # border_width,
            0,
            self.screen.root_depth,
            X.InputOutput,
            X.CopyFromParent,
            background_pixel=self.screen.black_pixel,
            border_pixel=self.screen.white_pixel,
            event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask
        )
        frame.change_attributes(event_mask=X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask | X.SubstructureRedirectMask | X.SubstructureNotifyMask)


        btn_size = border_width
        padding = 0

        frame_width = geom.width + 2 * border_width

        btn_close = frame.create_window(
            x=frame_width - 2 * (btn_size + padding),
            y=padding,
            width=btn_size,
            height=btn_size,
            border_width=1,
            depth=self.screen.root_depth,
            class_=X.InputOutput,
            visual=X.CopyFromParent,
            background_pixel=self.colormap.alloc_named_color(config["display"]["window"]["close"]["color"]).pixel,
            event_mask=X.ExposureMask | X.ButtonPressMask
        )
        btn_max = frame.create_window(
            x=frame_width - 3 * (btn_size + padding),
            y=padding,
            width=btn_size,
            height=btn_size,
            border_width=1,
            depth=self.screen.root_depth,
            class_=X.InputOutput,
            visual=X.CopyFromParent,
            background_pixel=self.colormap.alloc_named_color(config["display"]["window"]["maximize"]["color"]).pixel,
            event_mask=X.ExposureMask | X.ButtonPressMask
        )
        btn_min = frame.create_window(
            x=frame_width - 4 * (btn_size + padding),
            y=padding,
            width=btn_size,
            height=btn_size,
            border_width=1,
            depth=self.screen.root_depth,
            class_=X.InputOutput,
            visual=X.CopyFromParent,
            background_pixel=self.colormap.alloc_named_color(config["display"]["window"]["minimize"]["color"]).pixel,
            event_mask=X.ExposureMask | X.ButtonPressMask
        )

        btn_close.map()
        btn_max.map()
        btn_min.map()

        win.reparent(frame, border_width, border_width)

        
        frame.map()
        win.map()


        self.clients[win_id] = frame
        self.clients[frame.id] = win

        self.frame_to_button_mapping[frame.id] = (btn_close, btn_max, btn_min)

        self.frame_window_buttons[btn_close.id] = ("close", win)
        self.frame_window_buttons[btn_max.id] = ("maximize", win)
        self.frame_window_buttons[btn_min.id] = ("minimize", win)

        self.set_active_frame(frame)

    def handle_configure_request(self, event):
        values = {}
        if event.value_mask & X.CWX:
            values["x"] = event.x
        if event.value_mask & X.CWY:
            values["y"] = event.y
        if event.value_mask & X.CWWidth:
            values["width"] = event.width
        if event.value_mask & X.CWHeight:
            values["height"] = event.height
        if event.value_mask & X.CWBorderWidth:
            values["border_width"] = event.border_width
        if event.value_mask & X.CWSibling:
            values["sibling"] = event.above
        if event.value_mask & X.CWStackMode:
            values["stack_mode"] = event.stack_mode
        event.window.configure(**values)

    def handle_destroy_notify(self, event):
        win_id = event.window.id
        frame = self.clients.pop(win_id, None)
        if frame:
            logger.info(f"DestroyNotify - Destroying frame {frame.id} for window {win_id}")
            frame.destroy()
        else:
            for client_id, frm in list(self.clients.items()):
                if frm.id == win_id:
                    logger.info(f"DestroyNotify - Client already gone. Destroying frame {win_id}")
                    frm.destroy()
                    del self.clients[client_id]

    def handle_unmap_notify(self, event):
        win_id = event.window.id
        frame = self.clients.get(win_id)
        if frame:
            logger.debug(f"UnmapNotify - Unmapping frame {frame.id} for window {win_id}")
            frame.unmap()

if __name__ == "__main__":
    try:
        wm = SimplePyWM()
        wm.run()
    except:
        logger.error(traceback.format_exc())
        exit()