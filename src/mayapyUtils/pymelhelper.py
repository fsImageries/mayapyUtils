import pymel.core as pmc


def create_loc_on_pivot(selection=None, nameScheme=None):
    """
    Create locator on pivot of every selected or given node.
    If supplied node isn't a transform it checks for a parent 
    transform else it will skip the node.
    You can supply a nameScheme function to alter the name of 
    the generated locator on a per node base.

    Args:
        selection ([iterable], optional): List containing the nodes. Defaults to None.
        nameScheme ([Function], optional): Function to alter the name of the generated locators. 
                                           Defaults to None.
    """
    if not selection:
        selection = pmc.selected()

    assert selection, "Nothing selected."

    with pmc.UndoChunk():
        for node in selection:
            if node.type() != "transform":
                try:
                    par = pmc.listRelatives(node, ap=True)[0]

                    if par in selection:
                        continue
                    node = par
                except Exception:
                    continue

            name = node.name()
            if nameScheme:
                name = nameScheme(name)
            else:
                name = "{0}_loc".format(name)

            pos = node.getPivots(worldSpace=True)[0]
            loc = pmc.spaceLocator(n=name)

            pmc.move(loc, pos)
