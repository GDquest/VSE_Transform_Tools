import bpy
import bgl
import math
from mathutils import Vector
from mathutils.geometry import intersect_point_quad_2d

from .utils import get_strip_corners
from .utils import get_preview_offset
from .utils import mouse_to_res
from .utils import clear_rejects


def draw_callback_px_select(self, context):
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glLineWidth(4)

    theme = context.user_preferences.themes['Default']
    active_color = theme.view_3d.object_active
    select_color = theme.view_3d.object_selected

    active_strip = context.scene.sequence_editor.active_strip

    offset_x, offset_y, fac, preview_zoom = get_preview_offset()

    for strip in context.selected_sequences:
        if strip == active_strip:
            bgl.glColor4f(
                active_color[0], active_color[1], active_color[2],
                0.9 - (self.seconds / self.fadeout_duration)
            )
        else:
            bgl.glColor4f(
                select_color[0], select_color[1], select_color[2],
                0.9 - (self.seconds / self.fadeout_duration)
            )

        bgl.glBegin(bgl.GL_LINE_LOOP)
        corners = get_strip_corners(strip)
        for corner in corners:
            corner_x = int(corner[0] * preview_zoom * fac) + offset_x
            corner_y = int(corner[1] * preview_zoom * fac) + offset_y
            bgl.glVertex2i(corner_x, corner_y)
        bgl.glEnd()

    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)


class Select(bpy.types.Operator):
    bl_idname = "vse_transform_tools.select"
    bl_label = "Select Sequence"

    timer = None
    seconds = 0
    fadeout_duration = 0.20
    handle_select = None

    @classmethod
    def poll(self, context):
        if context.scene.sequence_editor:
            return True
        return False

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'TIMER':
            self.seconds += 0.01

        if self.seconds > self.fadeout_duration:
            context.window_manager.event_timer_remove(self.timer)
            bpy.types.SpaceSequenceEditor.draw_handler_remove(self.handle_select, 'PREVIEW')

            return {'FINISHED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        bpy.ops.vse_transform_tools.initialize_pivot()

        scene = context.scene

        mouse_x = event.mouse_region_x
        mouse_y = event.mouse_region_y

        mouse_vec = Vector([mouse_x, mouse_y])
        vector = mouse_to_res(mouse_vec)

        current_frame = scene.frame_current
        current_strips = []

        sequence_editor = scene.sequence_editor
        selection_list = []

        if len(scene.sequence_editor.meta_stack) > 0:
            strips = list(sequence_editor.meta_stack[-1].sequences)
        else:
            strips = list(scene.sequence_editor.sequences)

        rejects = []
        for strip in strips:
            if strip.type == 'SOUND':
                rejects.append(strip)
            if hasattr(strip, 'input_1'):
                rejects.append(strip.input_1)
            if hasattr(strip, 'input_2'):
                rejects.append(strip.input_2)

        strips = clear_rejects(strips, rejects)

        
        strips = sorted(strips, key=lambda strip: strip.channel)

        if 'MOUSE' in event.type:
            for strip in reversed(strips):
                start = strip.frame_start
                end = start + strip.frame_final_duration
                if (not strip.mute and
                        current_frame >= start and
                        current_frame <= end):

                    corners = get_strip_corners(strip)

                    bottom_left = Vector(corners[0])
                    top_left = Vector(corners[1])
                    top_right = Vector(corners[2])
                    bottom_right = Vector(corners[3])

                    intersects = intersect_point_quad_2d(
                        vector, bottom_left, top_left, top_right,
                        bottom_right)

                    if intersects and not event.type == 'A':
                        selection_list.append(strip)
                        if not event.shift:
                            bpy.ops.sequencer.select_all(action='DESELECT')
                            strip.select = True
                            bpy.context.scene.sequence_editor.active_strip = strip
                            break
                        else:
                            if not strip.select:
                                strip.select = True
                                bpy.context.scene.sequence_editor.active_strip = strip
                                break
                            else:
                                strip.select = True
                                break
                    if not selection_list and not event.shift and not event.type == 'A':
                        bpy.ops.sequencer.select_all(action='DESELECT')

                    if strip.blend_type in ['CROSS', 'REPLACE']:
                        return {'FINISHED'}

        elif event.type == 'A':
            rejects = []
            blocked_visibility = False
            for strip in reversed(strips):
                if blocked_visibility:
                    rejects.append(strip)
                if strip.blend_type in ['CROSS', 'REPLACE']:
                    blocked_visibility = True
            strips = clear_rejects(strips, rejects)

            all_selected = True
            for strip in strips:
                if not strip.select:
                    all_selected = False

            bpy.ops.sequencer.select_all(action='DESELECT')
            if not all_selected:
                for strip in strips:
                    strip.select = True

        args = (self, context)
        self.handle_select = bpy.types.SpaceSequenceEditor.draw_handler_add(
            draw_callback_px_select, args, 'PREVIEW', 'POST_PIXEL')

        self.timer = context.window_manager.event_timer_add(0.01, context.window)

        context.window_manager.modal_handler_add(self)

        return {'RUNNING_MODAL'}
