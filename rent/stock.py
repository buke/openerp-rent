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
from openerp.osv import osv, fields
from openerp import netsvc
from openerp.tools.translate import _

class stock_warehouse(osv.osv):
    _inherit = "stock.warehouse"
    _columns = {
        'lot_rent_id': fields.many2one('stock.location', 'Location Rent', required=True, domain=[('usage','=','internal')]),
        'lot_rent_send_id': fields.many2one('stock.location', 'Location Rent Send', required=True, domain=[('usage','=','internal')]),
        'lot_rent_return_id': fields.many2one('stock.location', 'Location Rent Return', required=True, domain=[('usage','=','internal')]),
    }

class stock_move(osv.osv):
    _inherit = "stock.move"
    _columns = {
        'rent_line_id': fields.many2one('rent.order.line', 'Rent Order Line', ondelete='set null', select=True, readonly=True),
    }

class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    _columns = {
        'rent_id': fields.many2one('rent.order', 'Rent Order', ondelete='set null', select=True),
        'rent_return_id': fields.many2one('rent.return', 'Return Order', ondelete='set null', select=True),

        'rent_state': fields.related('rent_id', 'state', type='char', string="Rent State", readonly=True),
        'rent_return_state': fields.related('rent_return_id', 'state', type='char', string="Rent Return State", readonly=True),

    }
    _defaults = {
        'rent_id': False,
        'rent_return_id': False
    }

    def action_done(self, cr, uid, ids, context=None):
        """ set rent order state = delivered until all pickings has done """
        ret = super(stock_picking, self).action_done(cr, uid, ids, context=context)
        for picking in self.browse(cr, uid, ids, context=context):
            # set rent.order to done
            if picking.rent_id and picking.rent_id.id:
                if all([p.state=="done" for p in picking.rent_id.picking_ids if p and p.id]):
                    wf_service = netsvc.LocalService('workflow')
                    wf_service.trg_validate(uid, 'rent.order', picking.rent_id.id, 'delivered', cr)

            # set rent.return to done
            if picking.rent_return_id and picking.rent_return_id.id:
                if all([p.state=="done" for p in picking.rent_return_id.picking_ids if p and p.id]):
                    wf_service = netsvc.LocalService('workflow')
                    wf_service.trg_validate(uid, 'rent.return', picking.rent_return_id.id, 'done', cr)

        return ret


# Redefinition of the new field in order to update the model stock.picking.out in the orm
# FIXME: this is a temporary workaround because of a framework bug (ref: lp996816). It should be removed as soon as
#        the bug is fixed
class stock_picking_out(osv.osv):
    _inherit = 'stock.picking.out'
    _columns = {
        'rent_id': fields.many2one('rent.order', 'Rent Order', ondelete='set null', select=True),
        'rent_return_id': fields.many2one('rent.return', 'Return Order', ondelete='set null', select=True),

        'rent_state': fields.related('rent_id', 'state', type='char', string="Rent State", readonly=True),
        'rent_return_state': fields.related('rent_return_id', 'state', type='char', string="Rent Return State", readonly=True),
    }



# Redefinition of the new field in order to update the model stock.picking.out in the orm
# FIXME: this is a temporary workaround because of a framework bug (ref: lp996816). It should be removed as soon as
#        the bug is fixed
class stock_picking_in(osv.osv):
    _inherit = 'stock.picking.in'
    _columns = {
        'rent_id': fields.many2one('rent.order', 'Rent Order', ondelete='set null', select=True),
        'rent_return_id': fields.many2one('rent.return', 'Return Order', ondelete='set null', select=True),

        'rent_state': fields.related('rent_id', 'state', type='char', string="Rent State", readonly=True),
        'rent_return_state': fields.related('rent_return_id', 'state', type='char', string="Rent Return State", readonly=True),
    }


class stock_return_picking(osv.osv_memory):
    _inherit = 'stock.return.picking'

    def view_init(self, cr, uid, fields_list, context=None):
        if context is None:
            context = {}
        res = super(stock_return_picking, self).view_init(cr, uid, fields_list, context=context)
        record_id = context and context.get('active_id', False)
        if record_id:
            pick_obj = self.pool.get('stock.picking')
            pick = pick_obj.browse(cr, uid, record_id, context=context)

            if pick.rent_id and pick.rent_id.state in ['returned', 'done']:
                raise osv.except_osv(_('Warning!'), _("You may only return rent pickings that are not Returned or Done!"))

            if pick.rent_return_id and pick.rent_return_id.state in ['done']:
                raise osv.except_osv(_('Warning!'), _("Rent return pickings can not be returned!"))
        return res


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
