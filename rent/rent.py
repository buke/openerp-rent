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
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
from openerp.osv import osv, fields
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from openerp import netsvc


class rent_order(osv.osv):
    _name = "rent.order"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Rent Order"
    #_track = {
    #}

    def _returned(self, cr, uid, ids, field_name, arg, context=None):
        if context is None:
            context = {}
        res = {}
        for rent in self.browse(cr, uid, ids, context=context):
            res[rent.id] = False
            if all([line.product_rent_qty==0 for line in rent.order_line]):
                res[rent.id] = True
        return res

    def _paid(self, cr, uid, ids, field_name, arg, context=None):
        if context is None:
            context = {}
        res = {}
        for rent in self.browse(cr, uid, ids, context=context):
            res[rent.id] = False
            if all([inv.state=='paid' for inv in rent.invoice_ids]):
                res[rent.id] = True
        return res

    def _invoiced(self, cr, uid, ids, field_name, arg, context=None):
        if context is None:
            context = {}
        res = {}
        for rent in self.browse(cr, uid, ids, context=context):
            res[rent.id] = False
            if rent.invoice_ids:
                res[rent.id] = True
        return res

    def _year_get_fnc(self, cr, uid, ids, name, unknow_none, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            if (record.date_order):
                res[record.id] = str(time.strptime(record.date_order, DEFAULT_SERVER_DATE_FORMAT).tm_year)
            else:
                res[record.id] = _('Unknown')
        return res

    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('rent.order.line').browse(cr, uid, ids, context=context):
            result[line.order_id.id] = True
        return result.keys()

    def _get_default_shop(self, cr, uid, context=None):
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        shop_ids = self.pool.get('sale.shop').search(cr, uid, [('company_id','=',company_id)], context=context)
        if not shop_ids:
            raise osv.except_osv(_('Error!'), _('There is no default shop for the current user\'s company!'))
        return shop_ids[0]

    def _get_default_journal(self, cr, uid, context=None):
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        journal_ids = self.pool.get('account.journal').search(cr, uid,
            [('type', '=', 'sale'), ('company_id', '=', company.id)],
            limit=1)
        if not journal_ids:
            raise osv.except_osv(_('Error!'),
                _('Please define sales journal for this company: "%s" (id:%d).') %
                (company.name, company.id))
        return journal_ids[0]

    def _amount_line_tax(self, cr, uid, line, context=None):
        val = 0.0
        for c in self.pool.get('account.tax').compute_all(cr, uid, line.tax_id, line.price_unit, line.product_uom_qty, line.product_id, line.order_id.partner_id)['taxes']:
            val += c.get('amount', 0.0)
        return val

    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
            }
            val = val1 = 0.0
            cur = order.pricelist_id.currency_id
            for line in order.order_line:
                val1 += line.price_subtotal
                val += self._amount_line_tax(cr, uid, line, context=context)
            res[order.id]['amount_tax'] = cur_obj.round(cr, uid, cur, val)
            res[order.id]['amount_untaxed'] = cur_obj.round(cr, uid, cur, val1)
            res[order.id]['amount_total'] = res[order.id]['amount_untaxed'] + res[order.id]['amount_tax']
        return res

    _columns = {
        'name': fields.char('Order Reference', size=64, required=True,
            readonly=True, states={'draft': [('readonly', False)]}, select=True),
        'order_line': fields.one2many('rent.order.line', 'order_id', 'Order Lines', readonly=True, states={'draft': [('readonly', False)]}),
        'shop_id': fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft': [('readonly', False)], 'cancel': [('readonly', False)]}),
        'origin': fields.char('Source Document', size=64),
        'client_order_ref': fields.char('Customer Reference', size=64),
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
        'line_id': fields.one2many('rent.order.line', 'order_id', 'Entry Lines'),
        'date_order': fields.date('Date', required=True, readonly=True, select=True, states={'draft': [('readonly', False)]}),
        'year': fields.function(_year_get_fnc, type="char", string='Year', store=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'date_accept': fields.date('Confirmation Date', readonly=True, select=True),
        'date_delivered': fields.date('Delivered Date', readonly=True, select=True),
        'date_return': fields.date('Return Date', readonly=True, select=True),
        'date_return_plan': fields.date('Plan Return Date', readonly=True, select=True, states={'draft': [('readonly', False)]}),
        'plan_invoiced': fields.boolean('Plan Invoiced'),
        'invoice_frequency': fields.selection([('one','One'), ('day', 'Daily'), ('woy','Weekly'), ('month','Monthly'), ('year','Yearly')], 'Recurring Invoice Frequency', readonly=True, required=True, select=True, states={'draft': [('readonly', False)]}),
        'invoice_frequency_time': fields.char('invoice_frequency_time', size=64),
        'user_id': fields.many2one('res.users', 'Salesperson', states={'draft': [('readonly', False)], }, select=True, track_visibility='onchange'),
        'partner_id': fields.many2one('res.partner', 'Customer', readonly=True, states={'draft': [('readonly', False)]}, required=True, change_default=True, select=True, track_visibility='always'),
        'partner_invoice_id': fields.many2one('res.partner', 'Invoice Address', readonly=True, required=True, states={'draft': [('readonly', False)]}),
        'partner_shipping_id': fields.many2one('res.partner', 'Delivery Address', readonly=True, required=True, states={'draft': [('readonly', False)]}),
        'pricelist_id': fields.many2one('product.pricelist', 'Pricelist', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'currency_id': fields.related('pricelist_id', 'currency_id', type="many2one", relation="res.currency", string="Currency", readonly=True, required=True),
        'project_id': fields.many2one('account.analytic.account', 'Contract / Analytic', readonly=True, states={'draft': [('readonly', False)]}),
        'invoice_ids': fields.many2many('account.invoice', 'rent_order_invoice_rel', 'order_id', 'invoice_id', 'Invoices', readonly=True),
        'picking_ids': fields.one2many('stock.picking.out', 'rent_id', 'Related Picking', readonly=True),
        'note': fields.text('Note'),
        'fiscal_position': fields.many2one('account.fiscal.position', 'Fiscal Position'),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, readonly=True, states={'draft':[('readonly',False)]}, domain=[('type','=','sale')]),
        'company_id': fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'amount_untaxed': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Untaxed Amount',
            store={
                'rent.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line'], 10),
                'rent.order.line': (_get_order, ['price_unit', 'tax_id', 'product_uom_qty'], 10),
            },
            multi='sums', track_visibility='always'),
        'amount_tax': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Taxes',
            store={
                'rent.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line'], 10),
                'rent.order.line': (_get_order, ['price_unit', 'tax_id', 'product_uom_qty'], 10),
            },
            multi='sums'),
        'amount_total': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Total',
            store={
                'rent.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line'], 10),
                'rent.order.line': (_get_order, ['price_unit', 'tax_id', 'product_uom_qty'], 10),
            },
            multi='sums'),

        'returned': fields.function(_returned, string='Returned', type="boolean"),
        'paid': fields.function(_paid, string='Paid', type="boolean"),
        'invoiced': fields.function(_invoiced, string='Invoiced', type="boolean"),
    }

    _defaults = {
        'date_order': fields.date.context_today,
        'invoice_frequency': 'day',
        'state': 'draft',
        'plan_invoiced': False,
        'user_id': lambda obj, cr, uid, context: uid,
        'name': lambda obj, cr, uid, context: '/',
        'shop_id': _get_default_shop,
        'partner_invoice_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['invoice'])['invoice'],
        'partner_shipping_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['delivery'])['delivery'],
        'journal_id': _get_default_journal,
    }

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Order Reference must be unique per Company!'),
    ]

    _order = 'id desc'

    def create(self, cr, uid, vals, context=None):
        if vals.get('name','/')=='/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'rent.order') or '/'

        return super(rent_order, self).create(cr, uid, vals, context=context)

    def onchange_pricelist_id(self, cr, uid, ids, pricelist_id, order_lines, context=None):
        context = context or {}
        if not pricelist_id:
            return {}
        value = {
            'currency_id': self.pool.get('product.pricelist').browse(cr, uid, pricelist_id, context=context).currency_id.id
        }
        if not order_lines:
            return {'value': value}
        warning = {
            'title': _('Pricelist Warning!'),
            'message' : _('If you change the pricelist of this order (and eventually the currency), prices of existing order lines will not be updated.')
        }
        return {'warning': warning, 'value': value}

    def onchange_shop_id(self, cr, uid, ids, shop_id, context=None):
        v = {}
        if shop_id:
            shop = self.pool.get('sale.shop').browse(cr, uid, shop_id, context=context)
            if shop.project_id.id:
                v['project_id'] = shop.project_id.id
            if shop.pricelist_id.id:
                v['pricelist_id'] = shop.pricelist_id.id
        return {'value': v}

    def onchange_partner_id(self, cr, uid, ids, part, context=None):
        if not part:
            return {'value': {'partner_invoice_id': False, 'partner_shipping_id': False,  'payment_term': False, 'fiscal_position': False}}

        part = self.pool.get('res.partner').browse(cr, uid, part, context=context)
        addr = self.pool.get('res.partner').address_get(cr, uid, [part.id], ['delivery', 'invoice', 'contact'])
        pricelist = part.property_product_pricelist_rent and part.property_product_pricelist_rent.id or False
        payment_term = part.property_payment_term and part.property_payment_term.id or False
        fiscal_position = part.property_account_position and part.property_account_position.id or False
        dedicated_salesman = part.user_id and part.user_id.id or uid
        val = {
            'partner_invoice_id': addr['invoice'],
            'partner_shipping_id': addr['delivery'],
            'payment_term': payment_term,
            'fiscal_position': fiscal_position,
            'user_id': dedicated_salesman,
        }
        if pricelist:
            val['pricelist_id'] = pricelist
        return {'value': val}


    def _generate_account_invoice(self, cr, uid, ids, context=None):
        """   generate account.invoice   """
        context = {} if context is None else context
        journal_obj = self.pool.get('account.journal')
        invoice_obj = self.pool.get('account.invoice')
        for rent in self.browse(cr, uid, ids, context=context):
            journal_ids = journal_obj.search(cr, uid,
                [('type', '=', 'sale'), ('company_id', '=', rent.company_id.id)],
                limit=1)
            if not journal_ids:
                raise osv.except_osv(_('Error!'),
                    _('Please define sales journal for this company: "%s" (id:%d).') %
                    (rent.company_id.name, rent.company_id.id))

            invoice_lines = []
            for line in rent.order_line:
                if line.product_id:
                    account_id = line.product_id.property_account_income.id
                    if not account_id:
                        account_id = line.product_id.categ_id.property_account_income_categ.id
                    if not account_id:
                        raise osv.except_osv(_('Error!'),
                                _('Please define income account for this product: "%s" (id:%d).') % \
                                    (line.product_id.name, line.product_id.id,))
                else:
                    prop = self.pool.get('ir.property').get(cr, uid,
                            'property_account_income_categ', 'product.category',
                            context=context)
                    account_id = prop and prop.id or False

                res = {
                    'name': line.name,
                    'sequence': line.sequence,
                    'origin': line.order_id.name,
                    'account_id': account_id,
                    'price_unit': line.price_unit,
                    'quantity': line.product_rent_qty,
                    'discount': 0,
                    'uos_id': line.product_uos.id,
                    'product_id': line.product_id.id or False,
                    'invoice_line_tax_id': [(6, 0, [x.id for x in line.tax_id])],
                    'account_analytic_id': line.order_id.project_id and line.order_id.project_id.id or False,
                }
                invoice_lines.append((0, 0, res))

            if not invoice_lines:
                continue

            invoice_vals = {
                'name': rent.client_order_ref or '',
                'origin': rent.name,
                'type': 'out_invoice',
                'reference': rent.client_order_ref or rent.name,
                'account_id': rent.partner_id.property_account_receivable.id,
                'partner_id': rent.partner_invoice_id.id,
                #'journal_id': rent.journal_id[0],
                'journal_id': rent.journal_id.id,
                'invoice_line': invoice_lines,
                'currency_id': rent.pricelist_id.currency_id.id,
                'comment': rent.note,
                #'payment_term': rent.payment_term and rent.payment_term.id or False,
                'fiscal_position': rent.fiscal_position.id or rent.partner_id.property_account_position.id,
                'date_invoice': context.get('date_invoice', False),
                'company_id': rent.company_id.id,
                'user_id': rent.user_id and rent.user_id.id or False
            }
            invoice_id = invoice_obj.create(cr, uid, invoice_vals, context=context)
            cr.execute('insert into rent_order_invoice_rel (order_id,invoice_id) values (%s,%s)', (rent.id, invoice_id))
            # confirm invoice
            wf_service = netsvc.LocalService('workflow')
            wf_service.trg_validate(uid, 'account.invoice', invoice_id, 'invoice_open', cr)

    def _generate_stock_picking(self, cr, uid, ids, context=None):
        """   generate stock.picking   """
        context = {} if context is None else context
        mod_obj = self.pool.get('ir.model.data')
        picking_obj = self.pool.get("stock.picking.out")
        model, stock_journal_id = mod_obj.get_object_reference(cr, uid, "rent", "journal_rent")
        for rent in self.browse(cr, uid, ids, context=context):
            picking_vals = {
                'rent_id': rent.id,
                'origin': rent.name,
                'stock_journal_id': stock_journal_id,
                'type': 'out',
                'move_type': 'one',
                'state': 'draft',
                'partner_id': rent.partner_id.id,
                'auto_picking': False,
                'company_id': rent.company_id.id,
            }
            move_lines = []
            for line in rent.order_line:
                if line.product_id.type == "service":
                    continue
                move_vals = {
                    "name": line.name,
                    "product_id": line.product_id.id,
                    "product_qty": line.product_uom_qty,
                    "product_uom": line.product_uom.id,
                    "type":"internal",
                    "location_id": rent.shop_id.warehouse_id.lot_rent_send_id.id,
                    "location_dest_id": rent.shop_id.warehouse_id.lot_rent_id.id,
                    "rent_line_id": line.id,
                    "partner_id": rent.partner_id.id, # not address
                }
                move_lines.append((0, 0, move_vals))

            if move_lines:
                picking_vals.update({'move_lines':move_lines})
                picking_id = picking_obj.create(cr, uid, picking_vals, context=context)
                picking_obj.draft_force_assign(cr, uid, [picking_id])

    def order_confirm(self, cr, uid, ids, context=None):
        """   workflow confirm   """
        for rent in self.browse(cr, uid, ids, context=context):
            if not rent.order_line:
                raise osv.except_osv(_('No Lines!'), _('Order Line can not be empty.'))

        return self.write(cr, uid, ids, {'state': 'confirmed'}, context=context)

    def order_accept(self, cr, uid, ids, context=None):
        """   workflow accepted   """
        self._generate_stock_picking(cr, uid, ids, context=context)
        return self.write(cr, uid, ids, {'state': 'accepted', 'date_accept': time.strftime('%Y-%m-%d')}, context=context)

    def order_canceled(self, cr, uid, ids, context=None):
        """   workflow cancel   """
        return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

    def order_done(self, cr, uid, ids, context=None):
        """   workflow done   """
        return self.write(cr, uid, ids, {'state': 'done'}, context=context)

    def order_delivered(self, cr, uid, ids, context=None):
        """   workflow delivered   """
        res = self.write(cr, uid, ids, {'state': 'delivered', 'date_delivered': time.strftime('%Y-%m-%d')}, context=context)
        self.cron_invoice_check(cr, uid, ids, context=context) # check for one
        return res

    def order_returned(self, cr, uid, ids, context=None):
        """   workflow returned   """
        res = self.write(cr, uid, ids, {'state': 'returned', 'date_return': time.strftime('%Y-%m-%d')}, context=context)
        return res

    def action_view_picking(self, cr, uid, ids, context=None):
        '''
        This function returns an action that display existing delivery orders of given sales order ids. It can either be a in a list or in a form view, if there is only one delivery order to show.
        '''
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')

        result = mod_obj.get_object_reference(cr, uid, 'stock', 'action_picking_tree')
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
            res = mod_obj.get_object_reference(cr, uid, 'stock', 'view_picking_out_form')
            result['views'] = [(res and res[1] or False, 'form')]
            result['res_id'] = pick_ids and pick_ids[0] or False
        return result

    def action_view_invoice(self, cr, uid, ids, context=None):
        '''
        This function returns an action that display existing delivery orders of given sales order ids. It can either be a in a list or in a form view, if there is only one delivery order to show.
        '''
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')

        result = mod_obj.get_object_reference(cr, uid, 'account', 'action_invoice_tree1')
        id = result and result[1] or False
        result = act_obj.read(cr, uid, [id], context=context)[0]
        #compute the number of delivery orders to display
        invoice_ids = []
        for rent in self.browse(cr, uid, ids, context=context):
            invoice_ids += [invoice.id for invoice in rent.invoice_ids]
        #choose the view_mode accordingly
        if len(invoice_ids) == 1:
            res = mod_obj.get_object_reference(cr, uid, 'account', 'invoice_form')
            result['views'] = [(res and res[1] or False, 'form')]
            result['res_id'] = invoice_ids and invoice_ids[0] or False
        else:
            result['domain'] = "[('id','in',["+','.join(map(str, invoice_ids))+"])]"

        return result

    def _generate_return_draft(self, cr, uid, ids, context=None):
        """   generate rent_return draft   """
        context = {} if context is None else context
        return_obj = self.pool.get('rent.return')

        return_ids = []

        for rent in self.browse(cr, uid, ids, context=context):
            if not rent.date_return_plan: continue
            return_vals = {
                'partner_id': rent.partner_id.id,
                'shop_id': rent.shop_id.id,
                'user_id': rent.user_id.id,
                'date_order': rent.date_return_plan,
                'reference': rent.name,
                'state': 'draft',
            }
            order_line = []
            for line in rent.order_line:
                if line.product_id.type == "service":
                    continue
                line_vals = {
                    'rent_order_line_id':line.id,
                    'rent_order_id':rent.id,
                    'name':line.name,
                    'product_id':line.product_id.id,
                    'product_uom_qty':line.product_rent_qty,
                    'product_rent_qty':line.product_rent_qty,
                    'product_uom':line.product_uom.id,
                }
                order_line.append((0, 0, line_vals))

            if order_line:
                return_vals.update({'order_line':order_line})
                return_id = return_obj.create(cr, uid, return_vals, context=context)
                return_ids.append(return_id)

        self.write(cr, uid, ids, {'plan_invoiced': True}, context=context)
        return return_ids

    def cron_invoice_check(self, cr, uid, ids=False, context=None):
        if context is None: context = {}
        if not ids:
            ids = self.search(cr, uid, [('state','in', ['delivered','returned'])], context=context)

        generate_ids = []
        return_draft_ids = []

        for rent in self.browse(cr, uid, ids, context=context):
            current_time = 'one' if rent.invoice_frequency == 'one' else ':'.join([rent.invoice_frequency, self.pool.get("ir.sequence")._interpolation_dict().get(rent.invoice_frequency)])

            if rent.invoice_frequency_time != current_time :
                generate_ids.append(rent.id)
                self.write(cr, uid, rent.id, {'invoice_frequency_time': current_time}, context=context)

            #generate rent.return draft
            if (not rent.plan_invoiced) and rent.date_return_plan and time.strptime(fields.date.context_today(self,cr,uid,context=context), DEFAULT_SERVER_DATE_FORMAT) >= time.strptime(rent.date_return_plan, DEFAULT_SERVER_DATE_FORMAT) :
                return_draft_ids.append(rent.id)

        self._generate_account_invoice(cr, uid, generate_ids, context=context)
        self._generate_return_draft(cr, uid, generate_ids, context=context)

    def button_dummy(self, cr, uid, ids, context=None):
        return True


class rent_order_line(osv.osv):

    def _product_rent_qty(self, cr, uid, ids, field_name, arg, context=None):
        #TODO make this field store or use sql script to get result
        if context is None:
            context = {}
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            rent_qty = return_qty = 0
            for move in line.move_ids:
                if move.state != "done" or move.partner_id.id !=line.order_partner_id.id: continue
                if move.location_dest_id.id == line.order_id.shop_id.warehouse_id.lot_rent_id.id:
                    rent_qty += move.product_qty
                if move.location_id.id == line.order_id.shop_id.warehouse_id.lot_rent_id.id:
                    return_qty += move.product_qty
            res[line.id] = rent_qty - return_qty
        return res

    def _amount_line(self, cr, uid, ids, field_name, arg, context=None):
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        res = {}
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            price = line.price_unit
            taxes = tax_obj.compute_all(cr, uid, line.tax_id, price, line.product_uom_qty, line.product_id, line.order_id.partner_id)
            cur = line.order_id.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, taxes['total'])
        return res

    def _get_uom_id(self, cr, uid, *args):
        try:
            proxy = self.pool.get('ir.model.data')
            result = proxy.get_object_reference(cr, uid, 'product', 'product_uom_unit')
            return result[1]
        except Exception, ex:
            return False

    _name = "rent.order.line"
    _description = "Rent Order Line"
    _columns = {
        'name': fields.text('Description', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'order_id': fields.many2one('rent.order', 'Rent Reference', required=True, ondelete='cascade', select=True, readonly=True, states={'draft':[('readonly',False)]}),
        'sequence': fields.integer('Sequence'),
        'product_id': fields.many2one('product.product', 'Product', domain=[('is_rent', '=', True)], change_default=True),
        'invoice_lines': fields.many2many('account.invoice.line', 'rent_order_line_invoice_rel', 'order_line_id', 'invoice_id', 'Invoice Lines', readonly=True),
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Product Price'), readonly=True, states={'draft': [('readonly', False)]}),
        'price_subtotal': fields.function(_amount_line, string='Subtotal', digits_compute= dp.get_precision('Account')),
        'tax_id': fields.many2many('account.tax', 'rent_order_tax', 'order_line_id', 'tax_id', 'Taxes', readonly=True, states={'draft': [('readonly', False)]}),
        'product_uom_qty': fields.float('Quantity', digits_compute= dp.get_precision('Product Unit of Measure'), required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure ', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'product_uos_qty': fields.float('Quantity (UoS)' ,digits_compute= dp.get_precision('Product UoS'), readonly=True, states={'draft': [('readonly', False)]}),
        'product_uos': fields.many2one('product.uom', 'Product UoS'),
        'product_rent_qty': fields.function(_product_rent_qty, string='Rent Quantity', digits_compute= dp.get_precision('Product UoS')),
        'th_weight': fields.float('Weight', readonly=True, states={'draft': [('readonly', False)]}),
        'move_ids': fields.one2many('stock.move', 'rent_line_id', 'Inventory Moves', readonly=True),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('cancel', 'Cancelled'),
            ('confirmed', 'Waiting Approval'),
            ('accepted', 'Approved'),
            ('returned', 'Returned'),
            ('done', 'Done'),
            ], 'Status', required=True, readonly=True),
        'order_partner_id': fields.related('order_id', 'partner_id', type='many2one', relation='res.partner', store=True, string='Customer'),
        'salesman_id':fields.related('order_id', 'user_id', type='many2one', relation='res.users', store=True, string='Salesperson'),
        'company_id': fields.related('order_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
    }

    _order = 'order_id desc, sequence, id'

    _defaults = {
        'product_uom' : _get_uom_id,
        'product_uom_qty': 1,
        'product_uos_qty': 1,
        'sequence': 10,
        'state': 'draft',
        'price_unit': 0.0,
    }

    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False, context=None):
        context = context or {}
        lang = lang or context.get('lang',False)
        if not  partner_id:
            raise osv.except_osv(_('No Customer Defined!'), _('Before choosing a product,\n select a customer in the sales form.'))
        warning = {}
        product_uom_obj = self.pool.get('product.uom')
        partner_obj = self.pool.get('res.partner')
        product_obj = self.pool.get('product.product')
        context = {'lang': lang, 'partner_id': partner_id}
        if partner_id:
            lang = partner_obj.browse(cr, uid, partner_id).lang
        context_partner = {'lang': lang, 'partner_id': partner_id}

        if not product:
            return {'value': {'th_weight': 0,
                'product_uos_qty': qty}, 'domain': {'product_uom': [],
                   'product_uos': []}}
        if not date_order:
            date_order = time.strftime(DEFAULT_SERVER_DATE_FORMAT)

        result = {}
        warning_msgs = ''
        product_obj = product_obj.browse(cr, uid, product, context=context_partner)

        uom2 = False
        if uom:
            uom2 = product_uom_obj.browse(cr, uid, uom)
            if product_obj.uom_id.category_id.id != uom2.category_id.id:
                uom = False
        if uos:
            if product_obj.uos_id:
                uos2 = product_uom_obj.browse(cr, uid, uos)
                if product_obj.uos_id.category_id.id != uos2.category_id.id:
                    uos = False
            else:
                uos = False
        fpos = fiscal_position and self.pool.get('account.fiscal.position').browse(cr, uid, fiscal_position) or False
        if update_tax: #The quantity only have changed
            result['tax_id'] = self.pool.get('account.fiscal.position').map_tax(cr, uid, fpos, product_obj.taxes_id)

        if not flag:
            result['name'] = self.pool.get('product.product').name_get(cr, uid, [product_obj.id], context=context_partner)[0][1]
            if product_obj.description_sale:
                result['name'] += '\n'+product_obj.description_sale
        domain = {}
        if (not uom) and (not uos):
            result['product_uom'] = product_obj.uom_id.id
            if product_obj.uos_id:
                result['product_uos'] = product_obj.uos_id.id
                result['product_uos_qty'] = qty * product_obj.uos_coeff
                uos_category_id = product_obj.uos_id.category_id.id
            else:
                result['product_uos'] = False
                result['product_uos_qty'] = qty
                uos_category_id = False
            result['th_weight'] = qty * product_obj.weight
            domain = {'product_uom':
                        [('category_id', '=', product_obj.uom_id.category_id.id)],
                        'product_uos':
                        [('category_id', '=', uos_category_id)]}
        elif uos and not uom: # only happens if uom is False
            result['product_uom'] = product_obj.uom_id and product_obj.uom_id.id
            result['product_uom_qty'] = qty_uos / product_obj.uos_coeff
            result['th_weight'] = result['product_uom_qty'] * product_obj.weight
        elif uom: # whether uos is set or not
            default_uom = product_obj.uom_id and product_obj.uom_id.id
            q = product_uom_obj._compute_qty(cr, uid, uom, qty, default_uom)
            if product_obj.uos_id:
                result['product_uos'] = product_obj.uos_id.id
                result['product_uos_qty'] = qty * product_obj.uos_coeff
            else:
                result['product_uos'] = False
                result['product_uos_qty'] = qty
            result['th_weight'] = q * product_obj.weight        # Round the quantity up

        if not uom2:
            uom2 = product_obj.uom_id
        # get unit price

        if not pricelist:
            warn_msg = _('You have to select a pricelist or a customer in the sales form !\n'
                    'Please set one before choosing a product.')
            warning_msgs += _("No Pricelist ! : ") + warn_msg +"\n\n"
        else:
            price = self.pool.get('product.pricelist').price_get(cr, uid, [pricelist],
                    product, qty or 1.0, partner_id, {
                        'uom': uom or result.get('product_uom'),
                        'date': date_order,
                        })[pricelist]
            if price is False:
                warn_msg = _("Cannot find a pricelist line matching this product and quantity.\n"
                        "You have to change either the product, the quantity or the pricelist.")

                warning_msgs += _("No valid pricelist line found ! :") + warn_msg +"\n\n"
            else:
                result.update({'price_unit': price})
        if warning_msgs:
            warning = {
                       'title': _('Configuration Error!'),
                       'message' : warning_msgs
                    }
        return {'value': result, 'domain': domain, 'warning': warning}

    def product_uom_change(self, cursor, user, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, context=None):
        context = context or {}
        lang = lang or ('lang' in context and context['lang'])
        if not uom:
            return {'value': {'price_unit': 0.0, 'product_uom' : uom or False}}
        return self.product_id_change(cursor, user, ids, pricelist, product,
                qty=qty, uom=uom, qty_uos=qty_uos, uos=uos, name=name,
                partner_id=partner_id, lang=lang, update_tax=update_tax,
                date_order=date_order, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
