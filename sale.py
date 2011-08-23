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
import netsvc
import datetime


class sale_order(osv.osv):
    _inherit = 'sale.order'

    _columns = {
        'container_id': fields.many2one('container.container', 'Container', help='Container of this sale order'),
    }

    def action_ship_create(self, cr, uid, ids, context=None):
        """
        Redefine action_ship_create method
        """
        stock_picking_obj = self.pool.get('stock.picking')
        stock_move_obj = self.pool.get('stock.move')
        procurement_order_obj = self.pool.get('procurement.order')
        sale_order_line_obj = self.pool.get('sale.order.line')
        wf_service = netsvc.LocalService("workflow")

        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id

        for sale_order in self.browse(cr, uid, ids, context=context):
            output_id = sale_order.shop_id.warehouse_id.lot_output_id.id
            picking_id = False

            for line in sale_order.order_line:
                proc_id = False
                date = datetime.datetime.now() + datetime.timedelta(line.delay or 0.0)
                date = (date - datetime.timedelta(company.security_lead)).strftime('%Y-%m-%d %H:%M:%S')

                if line.state == 'done':
                    continue

                if line.product_id and line.product_id.product_tmpl_id.type in ('product', 'consu'):
                    location_id = sale_order.shop_id.warehouse_id.lot_stock_id.id

                    if not picking_id:
                        loc_dest_id = sale_order.partner_id.property_stock_customer.id

                        picking_id = stock_picking_obj.create(cr, uid, {
                            'origin': sale_order.name,
                            'type': 'out',
                            'state': 'auto',
                            'move_type': sale_order.picking_policy,
                            'sale_id': sale_order.id,
                            'address_id': sale_order.partner_shipping_id.id,
                            'note': sale_order.note,
                            'invoice_state': (sale_order.order_policy == 'picking' and '2binvoiced') or 'none',
                            'container_id': sale_order.container_id and sale_order.container_id.id or False,
                        }, context=context)

                    move_id = stock_move_obj.create(cr, uid, {
                        'name': line.name[:64],
                        'picking_id': picking_id,
                        'product_id': line.product_id.id,
                        'date': date,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': line.product_uos_qty,
                        'product_uos': (line.product_uos and line.product_uos.id)\
                                or line.product_uom.id,
                        'product_packaging': line.product_packaging.id,
                        'address_id': line.address_allotment_id.id or sale_order.partner_shipping_id.id,
                        'location_id': location_id,
                        'location_dest_id': output_id,
                        'sale_line_id': line.id,
                        'tracking_id': False,
                        'state': 'draft',
                        'note': line.notes,
                    }, context=context)

                    procurement_id = procurement_order_obj.create(cr, uid, {
                        'name': sale_order.name,
                        'origin': sale_order.name,
                        'date': date,
                        'product_id': line.product_id.id,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': (line.product_uos and line.product_uos_qty) or line.product_uom_qty,
                        'product_uos': (line.product_uos and line.product_uos.id) or line.product_uom.id,
                        'location_id': sale_order.shop_id.warehouse_id.lot_stock_id.id,
                        'procure_method': line.type,
                        'move_id': move_id,
                        'property_ids': [(6, 0, [data.id for data in line.property_ids])],
                    }, context=context)

                    wf_service.trg_validate(uid, 'mrp.procurement', procurement_id, 'button_confirm', cr)
                    sale_order_line_obj.write(cr, uid, [line.id], {'procurement_id': procurement_id}, context=context)

                elif line.product_id and line.product_id.product_tmpl_id.type == 'service':
                    procurement_id = procurement_order_obj.create(cr, uid, {
                        'name': line.name,
                        'origin': sale_order.name,
                        'date': date,
                        'product_id': line.product_id.id,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'location_id': sale_order.shop_id.warehouse_id.lot_stock_id.id,
                        'procure_method': line.type,
                        'property_ids': [(6, 0, [x.id for x in line.property_ids])],
                    }, context=context)

                    wf_service.trg_validate(uid, 'mrp.procurement', procurement_id, 'button_confirm', cr)
                    sale_order_line_obj.write(cr, uid, [line.id], {'procurement_id': procurement_id}, context=context)

                else:
                    #
                    # No procurement because no product in the sale.order.line.
                    #
                    pass

            if picking_id:
                wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)

            val = {}
            if sale_order.state == 'shipping_except':
                val['state'] = 'progress'

                if (sale_order.order_policy == 'manual'):
                    for line in sale_order.order_line:
                        if (not line.invoiced) and (line.state not in ('cancel', 'draft')):
                            val['state'] = 'manual'
                            break

            self.write(cr, uid, [sale_order.id], val, context=context)

        return True

sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
