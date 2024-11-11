/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import {ListRenderer} from "@web/views/list/list_renderer";


patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.user = useService("user");
    },

    // get hasSelectors() {
    //     // return this.props.allowSelectors && !this.env.isSmall && (this.env.searchModel.tools.showSelector || Object.values(this.env.searchModel.searchItems).length===0 || this.env.inDialog);
    //     return this.props.allowSelectors && !this.env.isSmall && (this.env.searchModel.tools.showSelector || this.env.inDialog);
    // },

    shouldReverseHeader(column) {
        return false;
    }
})

// ListRenderer.template='jhy.ListRenderer'