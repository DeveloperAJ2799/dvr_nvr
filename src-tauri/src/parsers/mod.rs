use std::sync::Arc;

use crate::parsers::base::VendorParser;
use crate::parsers::generic_exported::GenericExportedParser;
use crate::parsers::registry::ParserRegistry;
use crate::parsers::stubs::{
    CpPlusParser, DahuaParser, GodrejParser, HikvisionParser, HoneywellParser, MatrixParser,
    TpLinkParser, UniviewParser,
};

pub mod base;
pub mod generic_exported;
pub mod registry;
pub mod stubs;

pub fn default_registry() -> ParserRegistry {
    let mut reg = ParserRegistry::new();
    reg.register(Arc::new(DahuaParser) as Arc<dyn VendorParser>);
    reg.register(Arc::new(HikvisionParser) as Arc<dyn VendorParser>);
    reg.register(Arc::new(UniviewParser) as Arc<dyn VendorParser>);
    reg.register(Arc::new(CpPlusParser) as Arc<dyn VendorParser>);
    reg.register(Arc::new(HoneywellParser) as Arc<dyn VendorParser>);
    reg.register(Arc::new(TpLinkParser) as Arc<dyn VendorParser>);
    reg.register(Arc::new(GodrejParser) as Arc<dyn VendorParser>);
    reg.register(Arc::new(MatrixParser) as Arc<dyn VendorParser>);
    reg.register(Arc::new(GenericExportedParser) as Arc<dyn VendorParser>);
    reg
}