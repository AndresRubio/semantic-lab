-- The Cumbre Coffee schema. load.rebuild drops every table named here and creates it again.

drop table if exists quality_incident, order_line, sales_order, customer, roast_batch_lot,
    roast_batch, product_flavour, product, lot_farm, lot, shipment, farm,
    cooperative_certification, cooperative, concept_closure, concept_alt_label, concept
    cascade;

create table concept (
    key text primary key,
    scheme text not null,
    iri text not null unique,
    label_en text not null,
    label_es text not null,
    parent_key text references concept (key)
);

create table concept_alt_label (
    concept_key text not null references concept (key),
    lang text not null,
    label text not null,
    primary key (concept_key, lang, label)
);

create table concept_closure (
    ancestor_key text not null references concept (key),
    descendant_key text not null references concept (key),
    depth integer not null check (depth >= 0),
    primary key (ancestor_key, descendant_key)
);

create table cooperative (
    code text primary key,
    name text not null,
    region_key text not null references concept (key)
);

create table cooperative_certification (
    cooperative_code text not null references cooperative (code),
    certification text not null check (certification in ('organic', 'fair_trade')),
    valid_from date not null,
    valid_until date,
    primary key (cooperative_code, certification, valid_from)
);

create table farm (
    code text primary key,
    name text not null,
    cooperative_code text not null references cooperative (code),
    altitude_m integer not null
);

create table shipment (
    code text primary key,
    origin_port text not null,
    destination_port text not null,
    departed_on date not null,
    arrived_on date not null
);

create table lot (
    code text primary key,
    cooperative_code text not null references cooperative (code),
    shipment_code text not null references shipment (code),
    process_key text not null references concept (key),
    variety text not null,
    harvested_on date not null,
    weight_kg numeric(10, 2) not null,
    price_per_kg numeric(8, 2) not null
);
create index lot_cooperative_code_idx on lot (cooperative_code);
create index lot_shipment_code_idx on lot (shipment_code);
create index lot_process_key_idx on lot (process_key);

create table lot_farm (
    lot_code text not null references lot (code),
    farm_code text not null references farm (code),
    primary key (lot_code, farm_code)
);

create table product (
    code text primary key,
    name text not null,
    category_key text not null references concept (key),
    origin_region_key text references concept (key),
    bag_weight_g integer not null,
    list_price numeric(8, 2) not null
);

create table product_flavour (
    product_code text not null references product (code),
    flavour_key text not null references concept (key),
    primary key (product_code, flavour_key)
);

create table roast_batch (
    code text primary key,
    product_code text not null references product (code),
    roasted_on date not null,
    output_kg numeric(8, 2) not null,
    cost_per_kg numeric(8, 2) not null
);

create table roast_batch_lot (
    roast_batch_code text not null references roast_batch (code),
    lot_code text not null references lot (code),
    share numeric(3, 2) not null check (share > 0 and share <= 1),
    primary key (roast_batch_code, lot_code)
);
create index roast_batch_lot_lot_code_idx on roast_batch_lot (lot_code);

create table customer (
    code text primary key,
    name text not null,
    segment text not null check (segment in ('cafe', 'shop', 'restaurant')),
    city text not null,
    country text not null
);

create table sales_order (
    code text primary key,
    customer_code text not null references customer (code),
    ordered_on date not null
);

create table order_line (
    order_code text not null references sales_order (code),
    line_no integer not null,
    product_code text not null references product (code),
    roast_batch_code text not null references roast_batch (code),
    bags integer not null,
    unit_price numeric(8, 2) not null,
    amount numeric(10, 2) not null,
    kg numeric(8, 3) not null,
    primary key (order_code, line_no)
);
create index order_line_product_code_idx on order_line (product_code);
create index order_line_roast_batch_code_idx on order_line (roast_batch_code);

create table quality_incident (
    code text primary key,
    lot_code text not null references lot (code),
    kind text not null check (kind in ('recall')),
    reported_on date not null,
    description text not null
);
