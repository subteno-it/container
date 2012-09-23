# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv
from osv import fields
from tools.translate import _
import itertools
import netsvc


class stock_partial_container_line(osv.osv_memory):
    _name = "stock.partial.container.line"
    _inherit = "stock.partial.move.line"
    _columns = {
        'wizard_id' : fields.many2one('stock.partial.container', string="Wizard", ondelete='CASCADE'),
    }

stock_partial_container_line()


class stock_partial_container(osv.osv_memory):
    _name = "stock.partial.container"
    _inherit = 'stock.partial.move'
    _description = "Container Partial Picking"

    def default_get(self, cr, uid, fields, context=None):
        """ To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary which of fields with values.
        """
        if context is None:
            context = {}

        res = {}
        container_ids = context.get('active_ids', [])
        if not container_ids or context.get('active_model') != 'stock.container':
            return res

        # Retrieve the list of moves to use
        container_obj = self.pool.get('stock.container')
        move_ids = [move.id for move in itertools.chain.from_iterable(
            [container.move_line_ids for container in container_obj.browse(cr, uid, container_ids, context=context)]
        ) if move.state == 'draft']

        # Call to super to create the moves in a good way
        res = super(stock_partial_container, self).default_get(cr, uid, fields, context=dict(context, active_ids=move_ids, active_model='stock.move'))

        return res

    _columns = {
        'move_ids' : fields.one2many('stock.partial.container.line', 'wizard_id', 'Moves'),
     }

    def do_partial(self, cr, uid, ids, context=None):
        """ Makes partial moves and pickings done.
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param fields: List of fields for which we want default values
        @param context: A standard dictionary
        @return: A dictionary which of fields with values.
        """
        container_obj = self.pool.get('stock.container')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")

        container_ids = context.get('active_ids', False)
        partial = self.browse(cr, uid, ids[0], context=context)

        for container in container_obj.browse(cr, uid, container_ids, context=context):
            moves_list = partial.move_ids
            for move in moves_list:
                #Adding a check whether any line has been added with new qty
                if not move.move_id:
                    raise osv.except_osv(_('Processing Error'), _('You cannot add any new move while validating the container, rather you can split the lines prior to validation!'))

                if move.move_id.product_uom.id != move.product_uom.id:
                    raise osv.except_osv(_('Processing Error'), _('You cannot change Unit of product!'))

                move_obj.write(cr, uid, [move.move_id.id], {
                    'product_qty': move.quantity,
                    'date': partial.date,
                    'state': 'done',
                })
                new_dates = container_obj.get_dates_from_moves(cr, uid, container.id, context=context)
                container_obj.write(cr, uid, [container.id], new_dates, context=context)
                wf_service.trg_validate(uid, 'stock.container', container.id, 'button_freight', cr)

        return {'type': 'ir.actions.act_window_close'}

stock_partial_container()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
