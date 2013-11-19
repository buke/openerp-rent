# -*- coding: utf-8 -*-
##############################################################################
#
#    rent
#    Copyright 2013 wangbuke <wangbuke@gmail.com>
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
import time
from openerp.osv import osv, fields
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from openerp import netsvc
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare

class rent_return(osv.osv):

    def _year_get_fnc(self, cr, uid, ids, name, unknow_none, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            if (record.date_order):
                res[record.id] = str(time.strptime(record.date_order, DEFAULT_SERVER_DATE_FORMAT).tm_year)
            else:
                res[record.id] = _('Unknown')
        return res

    def _get_default_shop(self, cr, uid, context=None):
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        shop_ids = self.pool.get('sale.shop').search(cr, uid, [('company_id','=',company_id)], context=context)
        if not shop_ids:
            raise osv.except_osv(_('Error!'), _('There is no default shop for the current user\'s company!'))
        return shop_ids[0]

    _name = "rent.return"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Rent Return"

    _columns = {
        'name': fields.char('Order Reference', size=64, required=True,
            readonly=True, states={'draft': [('readonly', False)]}, select=True),
        'partner_id': fields.many2one('res.partner', 'Customer', readonly=True, states={'draft': [('readonly', False)]}, required=True, change_default=True, select=True, track_visibility='always'),
        'shop_id': fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft': [('readonly', False)], 'cancel': [('readonly', False)]}),
        'user_id': fields.many2one('res.users', 'Receive person', states={'draft': [('readonly', False)], }, select=True, track_visibility='onchange'),
        'date_order': fields.date('Date', required=True, readonly=True, select=True, states={'draft': [('readonly', False)]}),
        'year': fields.function(_year_get_fnc, type="char", string='Year', store=True),
        'date_accept': fields.date('Approval Date', readonly=True, select=True),
        'order_line': fields.one2many('rent.return.line', 'order_id', 'Return Lines', readonly=True, states={'draft': [('readonly', False)]}),
        'picking_ids': fields.one2many('stock.picking.in', 'rent_return_id', 'Related Picking', readonly=True),
        'company_id': fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'reference': fields.char('Ref', size=64, readonly=True, states={'draft':[('readonly',False)]}),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('cancel', 'Cancelled'),
            ('confirmed', 'Waiting Approval'),
            ('accepted', 'Waiting Delivery'),
            ('done', 'Done'),
            ], 'Status', readonly=True, track_visibility='onchange',
            select=True),
        'note': fields.text('Note'),
    }

    _defaults = {
        'date_order': fields.date.context_today,
        'state': 'draft',
        'user_id': lambda obj, cr, uid, context: uid,
        'name': lambda obj, cr, uid, context: '/',
        'shop_id': _get_default_shop,
    }

    _order = 'id desc'

    def create(self, cr, uid, vals, context=None):
        if vals.get('name','/')=='/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'rent.return') or '/'
        return super(rent_return, self).create(cr, uid, vals, context=context)

    def onchange_partner_id(self, cr, uid, ids, partner_id, context=None):
        if not partner_id:
            return {}
        rent_obj = self.pool.get('rent.order')
        partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)

        order_lines = []
        rent_ids = rent_obj.search(cr, uid, [('partner_id', '=', partner.id), ('state', 'in', ['accepted', 'delivered'])], context=context)
        for rent in rent_obj.browse(cr, uid, rent_ids):
            for line in rent.order_line:
                if line.product_rent_qty <= 0: continue
                order_lines.append({
                    'rent_order_line_id':line.id,
                    'rent_order_id':rent.id,
                    'rent_order_date_order':rent.date_order,
                    'name':line.name,
                    'product_id':line.product_id.id,
                    'product_uom_qty':line.product_rent_qty,
                    'product_rent_qty':line.product_rent_qty,
                    'product_uom':line.product_uom.id,
                })
        val = {
            'user_id': partner.user_id and partner.user_id.id or uid,
            'order_line': order_lines,
        }
        return {'value': val}


    def action_view_picking(self, cr, uid, ids, context=None):
        '''
        This function returns an action that display existing delivery orders of given sales order ids. It can either be a in a list or in a form view, if there is only one delivery order to show.
        '''
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')

        result = mod_obj.get_object_reference(cr, uid, 'stock', 'action_picking_tree4')
        id = result and result[1] or False
        result = act_obj.read(cr, uid, [id], context=context)[0]
        #compute the number of delivery orders to display
        pick_ids = []
        for rent in self.browse(cr, uid, ids, context=context):
            pick_ids += [picking.id for picking in rent.picking_ids]
        #choose the view_mode accordingly
        if len(pick_ids) > 1:
            result['domain'] = "[('id','in',["+','.join(map(str, pick_ids))+"])]"
        else:
            res = mod_obj.get_object_reference(cr, uid, 'stock', 'view_picking_in_form')
            result['views'] = [(res and res[1] or False, 'form')]
            result['res_id'] = pick_ids and pick_ids[0] or False
        return result

    def _generate_stock_picking(self, cr, uid, ids, context=None):
        """   generate stock.picking   """
        context = {} if context is None else context
        mod_obj = self.pool.get('ir.model.data')
        model, stock_journal_id = mod_obj.get_object_reference(cr, uid, "rent", "journal_rent_return")

        for rent_return in self.browse(cr, uid, ids, context=context):
            picking_obj = self.pool.get("stock.picking.in")
            picking_vals = {
                'rent_return_id': rent_return.id,
                'origin': rent_return.name,
                'stock_journal_id': stock_journal_id,
                'type': 'in',
                'move_type': 'one',
                'state': 'draft',
                'partner_id': rent_return.partner_id.id,
                'auto_picking': False,
                'company_id': rent_return.company_id.id,
            }
            move_lines = []
            for line in rent_return.order_line:
                move_vals = {
                    "name": line.name,
                    "product_id": line.product_id.id,
                    "product_qty": line.product_uom_qty,
                    "product_uom": line.product_uom.id,
                    "type":"internal",
                    "location_id": rent_return.shop_id.warehouse_id.lot_rent_id.id,
                    "location_dest_id": rent_return.shop_id.warehouse_id.lot_rent_return_id.id,
                    "rent_line_id": line.rent_order_line_id.id,
                    "partner_id": rent_return.partner_id.id, # not address
                }
                move_lines.append((0, 0, move_vals))

            if move_lines:
                picking_vals.update({'move_lines':move_lines})
                picking_id = picking_obj.create(cr, uid, picking_vals, context=context)
                picking_obj.draft_force_assign(cr, uid, [picking_id])

    def return_confirm(self, cr, uid, ids, context=None):
        """   workflow confirm   """
        for rent_return in self.browse(cr, uid, ids, context=context):
            if not rent_return.order_line:
                raise osv.except_osv(_('No Lines!'), _('Line can not be empty.'))
        return self.write(cr, uid, ids, {'state': 'confirmed'}, context=context)

    def return_accept(self, cr, uid, ids, context=None):
        """   workflow confirm   """
        self._generate_stock_picking(cr, uid, ids, context=context)
        return self.write(cr, uid, ids, {'state': 'accepted', 'date_accept': time.strftime('%Y-%m-%d')}, context=context)

    def return_canceled(self, cr, uid, ids, context=None):
        """   workflow confirm   """
        return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

    def return_done(self, cr, uid, ids, context=None):
        """   workflow confirm   """
        #set rent.order to returned
        for rent_return in self.browse(cr, uid, ids, context=context):
            for line in rent_return.order_line:
                rent = line.rent_order_id
                if rent.returned:
                    wf_service = netsvc.LocalService('workflow')
                    wf_service.trg_validate(uid, 'rent.order', rent.id, 'returned', cr)

        return self.write(cr, uid, ids, {'state': 'done'}, context=context)


class rent_return_line(osv.osv):
    _name = "rent.return.line"
    _description = "Rent Return Line"
    _columns = {
        'name': fields.text('Description', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'sequence': fields.integer('Sequence'),
        'order_id': fields.many2one('rent.return', 'Rent Return Reference', required=True, ondelete='cascade', select=True, readonly=True, states={'draft':[('readonly',False)]}),
        'partner_id':fields.related('order_id', 'partner_id', type='many2one', relation='res.partner', string='Partner'),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True, domain=[('type','<>','service')], readonly=True),
        'product_uom_qty': fields.float('Return Quantity', digits_compute= dp.get_precision('Product Unit of Measure'), required=True, readonly=False, states={'draft': [('readonly', False)]}),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure ', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'product_uos_qty': fields.float('Quantity (UoS)' ,digits_compute= dp.get_precision('Product UoS'), readonly=True, states={'draft': [('readonly', False)]}),
        'product_uos': fields.many2one('product.uom', 'Product UoS'),
        'rent_order_line_id': fields.many2one('rent.order.line', 'Rent Line Reference', required=True, select=True, readonly=True),
        'rent_order_id':fields.related('rent_order_line_id', 'order_id', type='many2one', relation='rent.order', string='Rent Reference', readonly=True),
        'rent_order_date_order':fields.related('rent_order_id', 'date_order', type='date', string='Date Rent', readonly=True),
        'product_rent_qty':fields.related('rent_order_line_id', 'product_rent_qty', type='float',string='Rent Quantity', digits_compute= dp.get_precision('Product Unit of Measure'), readonly=True),
        'company_id': fields.related('order_id','company_id', relation='res.company', type='many2one', string='Company', store=True, readonly=True),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('cancel', 'Cancelled'),
            ('confirmed', 'Waiting Approval'),
            ('accepted', 'Waiting Delivery'),
            ('delivered', 'Delivered'),
            ('returned', 'Returned'),
            ('done', 'Done'),
            ], 'Status', readonly=True, track_visibility='onchange',
            select=True),
    }

    _order = 'order_id desc, sequence, id'

    _defaults = {
        'sequence': 10,
        'state': 'draft',
    }

    def onchange_product_uom_qty(self, cr, uid, ids, product_uom_qty, product_rent_qty, context=None):
        if product_uom_qty > product_rent_qty:
            val = {'product_uom_qty': product_rent_qty}
        elif product_uom_qty <= 0 :
            val = {'product_uom_qty': product_rent_qty}
        else:
            val = {'product_uom_qty': product_uom_qty}
        return {'value': val}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
