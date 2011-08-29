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


class stock_picking(osv.osv):
    _inherit = 'stock.picking'

    _columns = {
        'container_id': fields.many2one('container.container', 'Container', help='Container of this picking'),
    }

    def create(self, cr, uid, values, context=None):
        # Retrieve sale order id
        sale_order_id = values.get('sale_id', False)

        # Retrieve container id
        if sale_order_id:
            sale_order_data = self.pool.get('sale.order').read(cr, uid, sale_order_id, ['container_id'], context=context)
            # Add container_id in values
            values['container_id'] = sale_order_data and sale_order_data['container_id'] and sale_order_data['container_id'][0] or False

        # Call to standard behaviour
        id = super(stock_picking, self).create(cr, uid, values, context=context)

        return id

stock_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
