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
import datetime
from tools.translate import _
import netsvc


class container_container(osv.osv):
    _name = 'container.container'
    _description = 'Container'

    def _compute_values(self, cr, uid, ids, field_name, arg, context=None):
        """
        Computes weight, volume and remaining volume values
        """
        res = {}

        for container in self.browse(cr, uid, ids, context=context):
            weight = volume = 0.

            # Add values from each move
            for picking in container.incoming_picking_list_ids:
                for move in picking.move_lines:
                    weight += move.product_qty * move.product_id.weight_net
                    volume += move.product_qty * move.product_id.volume

            res[container.id] = {
                'weight': weight,
                'volume': volume,
                'remaining_volume': container.product_id.volume - volume,
            }

        return res

    _columns = {
        'name': fields.char('Name', size=64, required=True, help='Name of the container'),
        'partner_id': fields.many2one('res.partner', 'Freight Broker', readonly=True,
                                      states={'draft': [('readonly', False)], 'booking': [('readonly', False), ('required', True)]},
                                      help='Partner whom shipping container'),
        'address_id': fields.many2one('res.partner.address', 'Address to retrieve the container', readonly=True,
                                      states={'draft': [('readonly', False)], 'booking': [('readonly', False), ('required', True)]},
                                      help='Address whom the container is located, used to retrieve it'),
        'sscc': fields.char('SSCC', size=18, readonly=True,
                            states={'draft': [('readonly', False)], 'booking': [('readonly', False), ('required', True)]},
                            help='Serial Shipping Container Code : unique worldwide identifier for shipping units (given by the shipping company at booking). This field should be formatted to 18 numeric character.'),
        'etd_date': fields.date('Date of departure', readonly=True,
                                states={'draft': [('readonly', False)], 'booking': [('readonly', False), ('required', True)]},
                                help='Date of departure'),
        'eta_date': fields.date('Estimated date of arrival', readonly=True,
                                states={'booking': [('readonly', False), ('required', True)], 'freight': [('readonly', False), ('required', True)]},
                                help='Estimated date of arrival'),
        'etm_date': fields.date('Estimated time to market',
                                states={'draft': [('readonly', True)], 'unpacking': [('readonly', True)], 'cancel': [('readonly', True)], 'delivered': [('readonly', True)]},
                                help='Estimated date products available for delivery to customer'),
        'rda_date': fields.datetime('RDV', readonly=True,
                                    states={'approaching': [('required', True), ('readonly', False)]},
                                    help='Date and time at which the transporter will show up at final destination to deliver the container'),
        'weight': fields.function(_compute_values, method=True, string='Weight', type='float', store=False, multi='values', help='The total weight of all products listed in incoming picking lists of the container'),
        'volume': fields.function(_compute_values, method=True, string='Volume', type='float', store=False, multi='values', help='The total GROSS volume of all products listed in incoming picking lists of the container'),
        'remaining_volume': fields.function(_compute_values, method=True, string='Remaining Volume', type='float', store=False, multi='values', help='The substraction of the container product gross volume minus the total GROSS volume of all products listed in incoming picking lists of the container'),
        'product_id': fields.many2one('product.product', 'Product', required=True,
                                      states={'draft': [('readonly', False)]},
                                      help='The container product'),
        'incoterm_id': fields.many2one('stock.incoterms', 'Incoterm', required=True, help='Incoterm'),
        'container_stock_location_id': fields.many2one('stock.location', 'Container Stock Location', required=True, readonly=True,
                                                       states={'draft': [('readonly', False)]},
                                                       help='Stck location of the container\'s contents'),
        'destination_warehouse_id': fields.many2one('stock.warehouse', 'Destination Warehouse', required=True,
                                                    states={'cancel': [('readonly', True)], 'delivered': [('readonly', True)]},
                                                    help='Warehouse destination of the container\'s contents'),
        'incoming_picking_list_ids': fields.one2many('stock.picking', 'container_id', 'Incoming Picking List', domain=[('type', '=', 'in')], readonly=True,
                                                     states={'draft': [('readonly', False)]},
                                                     help='Incoming Picking List'),
        'outgoing_picking_list_ids': fields.one2many('stock.picking', 'container_id', 'Outgoing Picking List', domain=[('type', '=', 'out')], readonly=True, help='Outgoing Picking List'),
        'state': fields.selection([('draft', 'Draft'), ('booking', 'Booking'), ('freight', 'Freight'), ('clearance', 'Clearance'), ('approaching', 'Approaching'), ('unpacking', 'Unpacking'), ('delivered', 'Delivered'), ('cancel', 'Cancel')], 'Status', readonly=True, help='State of the container'),
        'prod_serial': fields.related('product_id', 'code', type='char', string='Product serial no.', help='Serial number of the product'),
    }

    _defaults = {
        'state': 'draft',
    }

    def check_etd_date(self, cr, uid, ids, context=None):
        """
        If Date of departure < planned date for one of the incoming stock moves : show alert message but still proceed
        """
        for container in self.browse(cr, uid, ids, context=context):
            for picking in container.incoming_picking_list_ids:
                # Error if the date of departure is before the planned date on at least one move
                if [move.id for move in picking.move_lines if container.etd_date and move.date and datetime.datetime.strptime(container.etd_date, '%Y-%m-%d') < datetime.datetime.strptime(move.date.split(' ')[0], '%Y-%m-%d')]:
                    raise osv.except_osv(_('Error!'), _('Date of departure %s < %s of planned date of stock move !') % (container.etd_date, move.date))

        return True

    def set_planned_date(self, cr, uid, ids, context=None):
        """
        Inside the outgoing picking list, set "planned dates" of all stock moves to the ETM date.
        """
        stock_move_obj = self.pool.get('stock.move')

        for container in self.browse(cr, uid, ids, context=context):
            move_ids = []

            # List moves to change
            for picking in container.outgoing_picking_list_ids:
                move_ids.extend([data.id for data in picking.move_lines])

            # Write new date on listed moves
            if move_ids and container.etd_date:
                stock_move_obj.write(cr, uid, move_ids, {'date': container.etd_date}, context=context)

        return True

    def create(self, cr, uid, values, context=None):
        """
        Create method
        """
        id = super(container_container, self).create(cr, uid, values, context=context)

        # Check date and set new if necessary
        if len(values.get('incoming_picking_list_ids', [])) and values.get('etd_date'):
            self.check_etd_date(cr, uid, [id], context=context)
            self.set_planned_date(cr, uid, [id], context=context)

        return id

    def write(self, cr, uid, ids, values, context=None):
        """
        Write method
        """
        res = super(container_container, self).write(cr, uid, ids, values, context=context)

        # Check date from incoming pickings
        if values.get('incoming_picking_list_ids', False) or values.get('etd_date', False):
            self.check_etd_date(cr, uid, ids, context=context)

        # Check date from outgoing pickings
        if values.get('outgoing_picking_list_ids', False) or values.get('etd_date', False):
            self.set_planned_date(cr, uid, ids, context=context)

        return res

    def action_booking(self, cr, uid, ids, context=None):
        """
        Action lanched when arriving on booking state
        """
        if context is None:
            # There is no context in workflow, so get it on user
            context = self.pool.get('res.users').context_get(cr, uid, context=context)

        stock_move_obj = self.pool.get('stock.move')
        stock_picking_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService('workflow')

        for container in self.browse(cr, uid, ids, context=context):
            # Check container's location
            if container.incoterm_id.code in ['EXW', 'FCA', 'FAS', 'FOB', 'CFR', 'CIF', 'CPT', 'CIP'] and container.container_stock_location_id.usage != 'internal':
                raise osv.except_osv(_('Warning !'), _('You must define container stock location as company location !'))
            elif container.incoterm_id.code in ['DAF', 'DES', 'DES', 'DDU', 'DDP'] and container.container_stock_location_id.usage != 'supplier':
                raise osv.except_osv(_('Warning !'), _('You must define container stock location as supplier location !'))

            # Check remaining volume
            if container.remaining_volume < 0:
                raise osv.except_osv(_('Warning !'), _('Remaining volume must be positive !'))

            move_ids = []
            picking_ids = []

            # Read incoming pickings list
            for picking in container.incoming_picking_list_ids:
                picking_ids.append(picking.id)
                move_ids.extend([data.id for data in picking.move_lines])

            # Changes incoming moves' location to container's location
            stock_move_obj.write(cr, uid, move_ids, {'location_dest_id': container.container_stock_location_id.id}, context=context)
            if picking_ids != stock_picking_obj.search(cr, uid, [('id', 'in', picking_ids), ('state', 'not in', ('done', 'cancel'))], context=context):
                raise osv.except_osv(_('Warning !'), _('Some Incoming packing list is in done or cancel state !'))

            # Confirm all incoming pickings
            for picking in picking_ids:
                wf_service.trg_validate(uid, 'stock.picking', picking, 'button_confirm', cr)

            # Set container's departure date if necessary
            date_done = False
            if not container.etd_date:
                for move in stock_move_obj.browse(cr, uid, move_ids, context=context):
                    if date_done and move.date:
                        if datetime.datetime.strptime(date_done, '%Y-%m-%d %H:%M:%S') < datetime.datetime.strptime(move.date, '%Y-%m-%d %H:%M:%S'):
                            date_done = move.date
                    elif not date_done:
                        date_done = move.date

                self.write(cr, uid, [container.id], {'etd_date': date_done}, context=context)

            # Set container's arrival date if necessary
            if not container.eta_date and date_done:
                date_eta = datetime.datetime.strptime(date_done, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(container.product_id.produce_delay or 0)
                self.write(cr, uid, [container.id], {'eta_date': date_eta.strftime('%Y-%m-%d')}, context=context)

            # Set container's market date if necessary
            if date_done:
                date_etm = datetime.datetime.strptime(date_done, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(container.product_id.sale_delay or 0)
                self.write(cr, uid, [container.id], {'etm_date': date_etm.strftime('%Y-%m-%d')}, context=context)

            # Create outgoing pickings from incoming pickings, and confirm all new created pickings
            default = {
                'state': 'draft',
                'type': 'out',
                'container_id': container.id,
            }
            copy_ids = []
            for picking in picking_ids:
                copy_id = stock_picking_obj.copy(cr, uid, picking, default, context=context)
                copy_ids.append(copy_id)
                wf_service.trg_validate(uid, 'stock.picking', copy_id, 'button_confirm', cr)

            # Set source and destination location on new outgoing picking's moves
            move_ids = stock_move_obj.search(cr, uid, [('picking_id', 'in', copy_ids)], context=context)
            values = {
                'location_id': container.container_stock_location_id.id,
                'location_dest_id': container.destination_warehouse_id and container.destination_warehouse_id.lot_input_id.id,
            }
            # Update new moves' date from container's market date
            if container.etm_date:
                values.update({'date': container.etm_date})

            stock_move_obj.write(cr, uid, move_ids, values, context=context)

        return True

    def action_freight(self, cr, uid, ids, context=None):
        """
        Action lanched when arriving on freight state
        """
        if context is None:
            # There is no context in workflow, so get it on user
            context = self.pool.get('res.users').context_get(cr, uid, context=context)

        stock_picking_obj = self.pool.get('stock.picking')

        picking_ids = []

        for container in self.browse(cr, uid, ids, context=context):
            # Error if date of departure is in the future
            if datetime.datetime.today() < datetime.datetime.strptime(container.etd_date, '%Y-%m-%d'):
                raise osv.except_osv(_('Warning !'), _('Current date is < Date of departure !'))

            # Add picking ids in the list
            picking_ids.extend([data.id for data in container.incoming_picking_list_ids])

        # Picking is now done
        stock_picking_obj.action_done(cr, uid, picking_ids, context=context)

        return True

    def action_clearance(self, cr, uid, ids, context=None):
        """
        Action lanched when arriving on clearance state
        """
        if context is None:
            # There is no context in workflow, so get it on user
            context = self.pool.get('res.users').context_get(cr, uid, context=context)

        # Error if the date of arrival is in the future
        if [container.id for container in self.browse(cr, uid, ids, context=context) if datetime.datetime.today() < datetime.datetime.strptime(container.eta_date, '%Y-%m-%d')]:
            raise osv.except_osv(_('Warning !'), _('Current date is < Estimated date of arrival !'))

        return True

    def action_unpacking(self, cr, uid, ids, context=None):
        """
        Action lanched when arriving on unpacking state
        """
        if context is None:
            # There is no context in workflow, so get it on user
            context = self.pool.get('res.users').context_get(cr, uid, context=context)

        # Error if the RDV date is in the past
        if [container.id for container in self.browse(cr, uid, ids, context) if datetime.datetime.today() > datetime.datetime.strptime(container.rda_date.split(' ')[0], '%Y-%m-%d')]:
            raise osv.except_osv(_('Warning !'), _('Current date is > RDV !'))

        return True

    def action_cancel(self, cr, uid, ids, context=None):
        """
        Action lanched when arriving on cancel state
        """
        if context is None:
            # There is no context in workflow, so get it on user
            context = self.pool.get('res.users').context_get(cr, uid, context=context)

        for container in self.browse(cr, uid, ids, context=context):
            # Error if one of the incoming pickings is in cancel state
            if [picking.id for picking in container.incoming_picking_list_ids if picking.state != "cancel"]:
                raise osv.except_osv(_('Warning !'), _('Incoming or outgoing packing list not in cancel state !'))

        return True

    def action_delivered(self, cr, uid, ids, context=None):
        """
        Action lanched when arriving on delivered state
        """
        if context is None:
            # There is no context in workflow, so get it on user
            context = self.pool.get('res.users').context_get(cr, uid, context=context)

        stock_move_obj = self.pool.get('stock.move')
        product_product_obj = self.pool.get('product.product')
        stock_picking_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")

        for container in self.browse(cr, uid, ids, context=context):
            # Retrieve total in quantity per product
            in_move_ids = stock_move_obj.search(cr, uid, [('picking_id.container_id', '=', container.id), ('picking_id.type', '=', 'in')], context=context)
            in_move_data = stock_move_obj.read(cr, uid, in_move_ids, ['product_id', 'product_qty'], context=context)
            in_product_qty = {}
            for in_move in in_move_data:
                in_product_qty[in_move['product_id'][0]] = in_product_qty.get(in_move['product_id'][0], 0) +  in_move['product_qty']

            # Retrieve total out quantity per product
            out_move_ids = stock_move_obj.search(cr, uid, [('picking_id.container_id', '=', container.id), ('picking_id.type', '=', 'in')], context=context)
            out_move_data = stock_move_obj.read(cr, uid, out_move_ids, ['product_id', 'product_qty'], context=context)
            out_product_qty = {}
            for out_move in out_move_data:
                out_product_qty[out_move['product_id'][0]] = out_product_qty.get(out_move['product_id'][0], 0) + out_move['product_qty']

            # Check incoming vs outgoing quantities
            picking = self.check_outgoing_incoming(cr, uid, out_product_qty, in_product_qty, context=context)
            if picking:
                raise osv.except_osv(_('Warning !'), _('Outgoing packing list product or qty is higher then Incoming packing !'))

            # Create new outgoing picking if there is unused quantity on some products, to store them in the container's warehouse
            picking = self.check_outgoing_incoming(cr, uid, in_product_qty, out_product_qty, context=context)
            if picking:
                values ={
                    'container_id': container.id,
                    'type': 'out',
                    'origin': 'created',
                }
                picking_id = stock_picking_obj.create(cr, uid, values, context=context)

                # Create moves in the new picking
                for key, val in picking.items():
                    product = product_product_obj.browse(cr, uid, key, context=context)
                    values = {
                        'product_id': key,
                        'product_uom': product.uom_id and product.uom_id.id or False,
                        'location_id': container.container_stock_location_id.id,
                        'location_dest_id': container.destination_warehouse_id and container.destination_warehouse_id.lot_input_id.id,
                        'date': container.etm_date,
                        'product_qty': val,
                        'picking_id': picking_id,
                        'name': product.name,
                    }
                    stock_move_obj.create(cr, uid, values, context=context)

                # Confirm the new picking
                wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)

            # Set all outgoing pickings' state to done
            move_ids = [data.id for data in container.outgoing_picking_list_ids]
            stock_picking_obj.action_done(cr, uid, move_ids, context=context)

        return True

    def check_outgoing_incoming(self, cr, uid, picking1, picking2, context=None):
        """
        Checks the waited or received quantities
        TODO : Check if the methods does the same thing after refactoring
        """
        picking_prod = {}

        for data in picking1:
            diff = min(max(0, picking1[data] - picking2[data]), picking1[data])
            if diff > 0:
                picking_prod[data] = diff

        return picking_prod

    def action_assign(self, cr, uid, ids, context=None):
        """
        Action lanched when arriving on assigned state
        """
        if context is None:
            # There is no context in workflow, so get it on user
            context = self.pool.get('res.users').context_get(cr, uid, context=context)

        stock_picking_obj = self.pool.get('stock.picking')

        for container in self.browse(cr, uid, ids, context=context):
            # Assign all incoming pickings
            picking_ids = [data.id for data in container.incoming_picking_list_ids]
            stock_picking_obj.action_assign(cr, uid, picking_ids, context)

        return True

container_container()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
