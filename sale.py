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
        'container_id': fields.many2one('container.container', 'Container', help='Container of this sale order line'),
    }

    def check_container_availability(self, cr, uid, ids, context=None):
        """
        Check if there is enough products available in selected containers and reserve if there is enough
        """
        container_container_obj = self.pool.get('container.container')
        stock_move_obj = self.pool.get('stock.move')

        sale_order_line_data = self.read(cr, uid, ids, ['product_id', 'product_uom_qty', 'container_id', 'move_ids'], context=context)
        for data in sale_order_line_data:
            if not data.get('container_id', False) or not data.get('product_id', False):
                continue

            # Retrieve quantity available in container
            stock_move_ids = stock_move_obj.search(cr, uid, [('picking_id', '=', False), ('container_id', '=', data['container_id'][0]), ('sale_line_id', '=', False), ('product_id', '=', data['product_id'][0])], context=context)
            stock_move_data = stock_move_obj.read(cr, uid, stock_move_ids, ['product_qty', 'move_dest_id'], context=context)
            if sum([move_data['product_qty'] for move_data in stock_move_data]) < data['product_uom_qty']:
                raise osv.except_osv(_('Not enough quantity'), _('%s\nNot enough quantity in selected container') % data['product_id'][1])

            # Reserve products in container
            qty_to_reserve = data['product_uom_qty']
            for move_data in stock_move_data:
                rest = qty_to_reserve - move_data['product_qty']

                # The move has too much quantity
                if rest < 0:
                    # Split the move
                    stock_move_obj.copy(cr, uid, move_data['id'], {'product_qty': -rest}, context=None)
                    stock_move_obj.write(cr, uid, [move_data['id']], {'product_qty': qty_to_reserve}, context=context)

                    # Update his move_dest_id
                    stock_move_obj.copy(cr, uid, move_data['move_dest_id'][0], {'product_qty': -rest}, context=None)
                    stock_move_obj.write(cr, uid, [move_data['move_dest_id'][0]], {'product_qty': qty_to_reserve, 'move_dest_id': data['move_ids'] and data['move_ids'][0]}, context=context)

                else:
                    # Update the move_dest_id of the move
                    stock_move_obj.write(cr, uid, [move_data['move_dest_id'][0]], {'move_dest_id': data['move_ids'] and data['move_ids'][0]}, context=context)

                # Set the sale_line_id on the move
                stock_move_obj.write(cr, uid, [move_data['id']], {'sale_line_id': data['id']}, context=context)

                # The move has not enough quantity, continue searching
                if rest > 0:
                    qty_to_reserve = rest
                    continue

                break

sale_order_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
