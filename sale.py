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
from tools import float_compare


class sale_order(osv.osv):
    _inherit = 'sale.order'

    def action_ship_create(self, cr, uid, ids, context=None):
        """
        Check if there is enough products available in lines' containers
        """
        res = super(sale_order, self).action_ship_create(cr, uid, ids, context)
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_line:
                if line.container_id:
                    line.check_container_availability(context=context)
        return res

    def _prepare_order_line_procurement(self, cr, uid, order, line, move_id, date_planned, context=None):
        """
        If we have a container filled, create a move for reserved product
        """
        if line.container_id:
            move_obj = self.pool.get('stock.move')
            loc_from_id = line.container_id.container_stock_location_id.id
            loc_to_id = line.container_id.destination_warehouse_id.lot_container_id \
                    and line.container_id.destination_warehouse_id.lot_container_id.id \
                    or order.partner_id.property_stock_customer.id
            new_move_id = move_obj.copy(cr, uid, move_id, {
                'location_id': loc_from_id,
                'location_dest_id': loc_to_id,
                'move_dest_id': move_id,
                'picking_id': False,
            }, context=None)
            move_obj.action_confirm(cr, uid, [new_move_id], context=context)
        return super(sale_order, self)._prepare_order_line_procurement(cr, uid, order, line, move_id, date_planned, context=context)

sale_order()


class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'

    _columns = {
        'container_id': fields.many2one('stock.container', 'Container', help='Container of this sale order line'),
    }

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Don't duplicate container
        """
        if not default:
            default = {}
        default['container_id'] = False
        return super(sale_order_line, self).copy_data(cr, uid, id, default, context=context)

    def onchange_check_product_on_container(self, cr, uid, ids, product_id, container_id, product_qty, context=None):
        """
        Check if this product is on thsi container
        """
        if (not product_id) or (not container_id):
            return {}
        if context is None:
            context = self.pool.get('res.users').context_get(cr, uid)
        res = {}
        move_obj = self.pool.get('stock.move')
        move_ids = move_obj.search(cr, uid, [
            ('picking_id', '=', False),
            ('container_id', '=', container_id),
            ('sale_line_id', '=', False),
            ('product_id', '=', product_id),
        ], context=context)
        if not move_ids:
            res['warning'] = {
                'title': _('Product not found'),
                'message': _('This product is not available on this container\nChoose another one'),
            }
            res['value'] = {'container_id': False}
        else:
            # Check if there enougth qty on the container
            moves = move_obj.browse(cr, uid, move_ids, context=context)
            product_sum = sum([move.product_qty for move in moves])
            if product_sum < product_qty:
                res['warning'] = {
                    'title': _('Insuffisant Quantity'),
                    'message': _('The quantity for this product is not enougth on this container (only %.2f)\nChoose another one') % product_sum,
                }
                res['value'] = {'container_id': False}
        return res

    def check_container_availability(self, cr, uid, ids, context=None):
        """
        Check if there is enough products available in selected containers
        """
        if context is None:
            context = {}
        container_obj = self.pool.get('stock.container')
        product_uom_obj = self.pool.get('product.uom')
        for line in self.browse(cr, uid, ids, context=context):
            if not line.container_id or not line.product_id:
                continue
            # Retrieve quantity available in container
            ctx = dict(context, product_id=line.product_id.id)
            container = container_obj.browse(cr, uid, line.container_id.id, context=ctx)
            qty = product_uom_obj._compute_qty(cr, uid, line.product_uom.id, line.product_uom_qty, line.product_id.uom_id.id)
            # Stock virtual is negative
            compare_qty = float_compare(container.stock_real + container.stock_virtual, qty, precision_rounding=line.product_id.uom_id.rounding)
            if container.stock_virtual > 0 and compare_qty == -1:
                raise osv.except_osv(_('Not enough quantity'),
                                     _('%s\nNot enough quantity in container %s') % (line.product_id.name, line.container_id.name))
        return True


sale_order_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
