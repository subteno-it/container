# -*- coding: utf-8 -*-
##############################################################################
#
#    container module for OpenERP, Manages containers receipt
#    Copyright (C) 2011 SYLEAM Info Services (<http://www.Syleam.fr/>)
#              Sylvain Garancher <sylvain.garancher@syleam.fr>
#
#    This file is a part of container
#
#    container is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    container is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


from osv import osv
from osv import fields


class stock_move(osv.osv):
    _inherit = 'stock.move'

    _columns = {
        'container_id': fields.many2one('stock.container', 'Container', help='Container of this move'),
    }

stock_move()

class stock_picking(osv.osv):
    _inherit = 'stock.picking'

    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        if context is None:
            context = {}
        res = super(stock_picking, self).do_partial(cr, uid, ids, partial_datas, context=context)
        container_ids = context.get('container_ids', [])
        # Check if in a container
        if container_ids:
            move_obj = self.pool.get('stock.move')
            container_obj = self.pool.get('stock.container')
            for container in container_obj.browse(cr, uid, container_ids, context=context):
                for picking in self.browse(cr, uid, ids, context=context):
                    # Check if backorder, if yes, we must remove this picking of container and change location_id in stock move
                    if picking.backorder_id:
                        #FIXME : if not find partner ??
                        if picking.partner_id:
                            loc_id = picking.partner_id.property_stock_supplier.id
                            for move in picking.move_lines:
                                move_obj.write(cr, uid, [move.id], {'location_id': loc_id}, context=context)
                                container_obj.write(cr, uid, [container.id], {'incoming_move_list_ids': [(3, move.id)]}, context=context)
                        for move_backorder in picking.backorder_id.move_lines:
                            container_obj.write(cr, uid, [container.id], {'incoming_move_list_ids': [(4, move_backorder.id)]}, context=context)
        return res

stock_picking()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
