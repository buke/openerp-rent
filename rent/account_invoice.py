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

class account_invoice(osv.osv):
    _inherit = "account.invoice"
    _columns = {
        'rent_ids': fields.many2many('rent.order', 'rent_order_invoice_rel', 'invoice_id', 'order_id', 'Rents', readonly=True),
    }

    def confirm_paid(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        res = super(account_invoice, self).confirm_paid(cr, uid, ids, context=context)
        for invoice in self.browse(cr, uid, ids, context=context):
            for rent in invoice.rent_ids:
                if rent.paid:
                    wf_service = netsvc.LocalService('workflow')
                    wf_service.trg_validate(uid, 'rent.order', rent.id, 'done', cr)
        return res



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
