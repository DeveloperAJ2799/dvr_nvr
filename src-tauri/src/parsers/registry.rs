use std::sync::Arc;

use crate::parsers::base::VendorParser;

pub struct ParserRegistry {
    parsers: Vec<Arc<dyn VendorParser>>,
}

impl ParserRegistry {
    pub fn new() -> Self {
        Self {
            parsers: Vec::new(),
        }
    }

    pub fn register(&mut self, parser: Arc<dyn VendorParser>) {
        self.parsers.push(parser);
    }

    pub fn list(&self) -> Vec<ParserInfo> {
        let mut infos: Vec<ParserInfo> = self
            .parsers
            .iter()
            .map(|p| ParserInfo {
                vendor: p.vendor_name(),
                vendor_id: p.vendor_id().to_string(),
                priority: p.priority(),
                description: p.description(),
            })
            .collect();
        infos.sort_by(|a, b| b.priority.cmp(&a.priority).then(a.vendor.cmp(&b.vendor)));
        infos
    }

    pub fn get(&self, vendor_id: &str) -> Option<Arc<dyn VendorParser>> {
        self.parsers
            .iter()
            .find(|p| p.vendor_id() == vendor_id)
            .cloned()
    }

    pub fn all(&self) -> Vec<Arc<dyn VendorParser>> {
        self.parsers.clone()
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ParserInfo {
    pub vendor: String,
    pub vendor_id: String,
    pub priority: u8,
    pub description: String,
}

impl Default for ParserRegistry {
    fn default() -> Self {
        Self::new()
    }
}