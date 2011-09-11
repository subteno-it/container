
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

from osv import fields, osv
from tools.translate import _
import time
import netsvc

class stock_partial_container(osv.osv_memory):
    _name = "stock.partial.container"
    _description = "Container Partial Picking"
    _columns = {
        'date': fields.datetime('Date', required=True),
        'product_moves' : fields.one2many('stock.move.memory.in', 'wizard_id', 'Moves'),
     }

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

        container_obj = self.pool.get('stock.container')
        res = super(stock_partial_container, self).default_get(cr, uid, fields, context=context)
        container_ids = context.get('active_ids', [])
        if not container_ids:
            return res

        result = []
        for container in container_obj.browse(cr, uid, container_ids, context=context):
            for move in container.move_line_ids:
                if move.state in ('draft'):
                    result.append(self.__create_partial_container_memory(move))

        if 'product_moves' in fields:
            res.update({'product_moves': result})
        if 'date' in fields:
            res.update({'date': time.strftime('%Y-%m-%d %H:%M:%S')})
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        result = super(stock_partial_container, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

        container_obj = self.pool.get('stock.container')
        container_ids = context.get('active_ids', False)

        if not container_ids:
            # not called through an action (e.g. buildbot), return the default.
            return result

        _moves_arch_lst = """<form string="%s">
                        <field name="date"/>
                        <separator colspan="4" string="%s"/>
                        <field name="%s" colspan="4" nolabel="1" mode="tree,form" width="550" height="200" ></field>
                        """ % (_('Process Document'), _('Products'), "product_moves")
        _moves_fields = result['fields']

        # add field related to picking type only
        _moves_fields.update({
                            'product_moves' : {'relation': 'stock.move.memory.in', 'type' : 'one2many', 'string' : 'Product Moves'},
                            })

        _moves_arch_lst += """
                <separator string="" colspan="4" />
                <label string="" colspan="2"/>
                <group col="2" colspan="2">
                <button icon='gtk-cancel' special="cancel"
                    string="_Cancel" />
                <button name="do_partial" string="_Validate"
                    colspan="1" type="object" icon="gtk-go-forward" />
            </group>
        </form>"""
        result['arch'] = _moves_arch_lst
        result['fields'] = _moves_fields
        return result

    def __create_partial_container_memory(self, move):
        move_memory = {
            'product_id' : move.product_id.id,
            'quantity' : move.product_qty,
            'product_uom' : move.product_uom.id,
            'prodlot_id' : move.prodlot_id.id,
            'move_id' : move.id,
        }

        return move_memory

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
        uom_obj = self.pool.get('product.uom')
        wf_service = netsvc.LocalService("workflow")

        container_ids = context.get('active_ids', False)
        partial = self.browse(cr, uid, ids[0], context=context)
        partial_datas = {
            'delivery_date' : partial.date
        }

        for container in container_obj.browse(cr, uid, container_ids, context=context):
            moves_list = partial.product_moves
            for move in moves_list:
                #Adding a check whether any line has been added with new qty
                if not move.move_id:
                    raise osv.except_osv(_('Processing Error'),\
                    _('You cannot add any new move while validating the container, rather you can split the lines prior to validation!'))

                if move.move_id.product_uom.id != move.product_uom.id:
                    raise osv.except_osv(_('Processing Error'),\
                    _('You cannot change Unit of product!'))

                move_obj.write(cr, uid, [move.move_id.id],
                        {
                            'product_qty' : move.quantity,
                            'date' : partial.date,
                            'state': 'done',
                        })
                container_obj.write(cr, uid, [container.id], {'etd_date': partial.date}, context=context)
                wf_service.trg_validate(uid, 'stock.container', container.id, 'button_freight', cr)

        return {'type': 'ir.actions.act_window_close'}

stock_partial_container()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
