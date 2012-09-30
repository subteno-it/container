# -*- coding: utf-8 -*-
##############################################################################
#
#    container module for OpenERP, Manages containers receipt
#    Copyright (C) 2011 SYLEAM Info Services (<http://www.Syleam.fr/>)
#              Sylvain Garancher <sylvain.garancher@syleam.fr>
#              Sebastien LANGE <sebastien.lange@syleam.fr>
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
from tools.translate import _


class sale_order(osv.osv):
    _inherit = 'sale.order'

    def action_ship_create(self, cr, uid, ids, context=None):
        """
        Check if there is enough products available in lines' containers
        """
        res = super(sale_order, self).action_ship_create(cr, uid, ids, context)
        for order in self.browse(cr, uid, ids, context=context):
            for sale_order_line in order.order_line:
                sale_order_line.check_container_availability(context=context)
        return res

sale_order()


class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'

    _columns = {
        'container_id': fields.many2one('stock.container', 'Container', help='Container of this sale order line'),
    }

    def check_container_availability(self, cr, uid, ids, context=None):
        """
        Check if there is enough products available in selected containers and reserve if there is enough
        """
        move_obj = self.pool.get('stock.move')
        for line in self.browse(cr, uid, ids, context=context):
            if not line.container_id or not line.product_id:
                continue
            # Retrieve quantity available in container
            move_ids = move_obj.search(cr, uid, [
                ('picking_id', '=', False),
                ('container_id', '=', line.container_id.id),
                ('sale_line_id', '=', False),
                ('product_id', '=', line.product_id.id),
            ], context=context)
            moves = move_obj.browse(cr, uid, move_ids, context=context)
            if sum([move.product_qty for move in moves]) < line.product_uom_qty:
                raise osv.except_osv(_('Not enough quantity'), _('%s\nNot enough quantity in selected container') % line.product_id.id)
            # Reserve products in container
            qty_to_reserve = line.product_uom_qty
            for move in moves:
                rest = qty_to_reserve - move.product_qty
                # The move has too much quantity
                if rest < 0:
                    # Split the move
                    move_obj.copy(cr, uid, move.id, {'product_qty': -rest}, context=None)
                    move_obj.write(cr, uid, [move.id], {'product_qty': qty_to_reserve}, context=context)
                    # Update his move_dest_id
                    move_obj.copy(cr, uid, move.move_dest_id.id, {'product_qty': -rest}, context=None)
                    move_obj.write(cr, uid, [move.move_dest_id.id], {'product_qty': qty_to_reserve, 'move_dest_id': line.move_ids and line.move_ids[0].id}, context=context)
                else:
                    # Update the move_dest_id of the move
                    move_obj.write(cr, uid, [move.move_dest_id.id], {'move_dest_id': line.move_ids and line.move_ids[0].id}, context=context)
                # Set the sale_line_id on the move
                move_obj.write(cr, uid, [move.id], {'sale_line_id': line.id}, context=context)
                # The move has not enough quantity, continue searching
                if rest > 0:
                    qty_to_reserve = rest
                    continue
                break

sale_order_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
