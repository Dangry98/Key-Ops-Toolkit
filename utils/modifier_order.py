"""Where modifiers go in the stack, so shading always comes out right.

Shape modifiers (Bevel, Array, Mirror, Solidify...) come first, shading modifiers last, in this order:
Triangulate, then Weighted Normal, then Smooth by Angle / Auto Smooth. Modifiers pinned to the end
(use_pin_to_last, Blender 4.2+) always stay below everything else, in their own order.
"""

import bpy

# lower sorts later in the stack; None: a shape modifier (keeps its place among the shape modifiers)
SHADING_RANK = {'TRIANGULATE': 1, 'WEIGHTED_NORMAL': 2}
SMOOTH_NAMES = ("Smooth by Angle", "Auto Smooth")


def shading_rank(mod):
    """How late a shading modifier belongs (higher = later), or 0 for a shape modifier."""
    if mod.type in SHADING_RANK:
        return SHADING_RANK[mod.type]
    if mod.type == 'NODES' and (any(n in mod.name for n in SMOOTH_NAMES)
                                or (mod.node_group and any(n in mod.node_group.name for n in SMOOTH_NAMES))):
        return 3
    return 0


def pinned(mod):
    return bool(getattr(mod, "use_pin_to_last", False))


def place_shape_modifier(obj, mod):
    """Move a shape modifier (just added at the bottom) above every shading and pinned modifier."""
    mods = obj.modifiers
    idx = mods.find(mod.name)
    target = idx
    for i, m in enumerate(mods):
        if i >= idx:
            break
        if shading_rank(m) or pinned(m):
            target = i
            break
    if target != idx:
        mods.move(idx, target)
    return target


def sort_shading_last(obj):
    """Put every shading modifier after the shape modifiers, in shading order, keeping the shape modifiers'
    order and leaving pinned modifiers at the end. Returns True when anything moved."""
    mods = obj.modifiers
    names = [m.name for m in mods if not pinned(m)]
    shape = [n for n in names if not shading_rank(mods[n])]
    shading = sorted((n for n in names if shading_rank(mods[n])), key=lambda n: shading_rank(mods[n]))
    want = shape + shading
    if want == names:
        return False
    for i, name in enumerate(want):
        cur = mods.find(name)
        if cur != i:
            mods.move(cur, i)
    return True


def can_move(obj, mod, new_index):
    """A move within the stack that never crosses into the pinned modifiers at the end."""
    mods = obj.modifiers
    if not 0 <= new_index < len(mods) or pinned(mod):
        return False
    return not pinned(mods[new_index])
