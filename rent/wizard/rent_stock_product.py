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

from openerp.osv import fields, osv
from openerp.tools.translate import _

class rent_stock_product(osv.osv_memory):
    _name = "rent.stock.product"
    _description = "Rent Products by Partner"
    _columns = {
            'partner_id': fields.many2one('res.partner', 'Customer', required=True),
            'include_childs': fields.boolean('Include Childs'),
            'from_date': fields.datetime('From'),
            'to_date': fields.datetime('To'),
            'type': fields.selection([('inventory','Analyse Current Inventory'),
                ('period','Analyse a Period')], 'Analyse Type', required=True),
            }
    _defaults = {
        'partner_id': lambda s, cr, uid, c: c.get('active_id'),
        'include_childs': True,
        'type': 'inventory',
    }

    def action_open_window(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if ids and ids[0]:
            rent_location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'rent', 'stock_location_rent')[1]
            stock_product = self.browse(cr, uid, ids[0], context=context)
            if not stock_product.include_childs:
                rent_partner_ids = [stock_product.partner_id.id]
            else:
                rent_partner_ids =self.pool.get('res.partner').search(cr, uid, [('parent_id', 'child_of', [stock_product.partner_id.id])], context=context)

            return {
                'name': _('Current Inventory'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'product.product',
                'type': 'ir.actions.act_window',
                'context': {
                    'location': rent_location_id,
                    'rent_partner_id': stock_product.partner_id.id,
                    'rent_partner_ids': rent_partner_ids,
                    'from_date': stock_product.from_date,
                    'to_date': stock_product.to_date,
                    },
                'domain': [('type', '<>', 'service'), ('is_rent','=','True')],
            }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
