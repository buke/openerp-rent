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
{
    'name': 'Rent module',
    'version': '0.1',
    'category': 'Sales Management',
    'description': """
""",
    'author': 'wangbuke@gmail.com',
    'website': 'http://buke.github.io',
    'depends': ['sale', 'stock'],
    'installable': True,
    'images': [],
    'data': [
        'security/rent_security.xml',
        'product_data.xml',
        'stock_data.xml',
        'rent_data.xml',
        'rent_return_data.xml',

        'rent_sequence.xml',
        'rent_workflow.xml',
        'rent_view.xml',

        'rent_return_sequence.xml',
        'rent_return_workflow.xml',
        'rent_return_view.xml',

        'wizard/rent_stock_product_view.xml',
        'product_view.xml',
        'stock_view.xml',
        'res_partner_view.xml',

    ],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
