import dataclasses

from semantic_lab.domain.records import Dataset


def first_orders(dataset: Dataset, count: int) -> Dataset:
    """The first `count` orders with their lines, the batches the lines name and those batches'
    components. Every other table stays whole, and no row names one that was cut."""
    if count < 0:
        raise ValueError(f"count must not be negative, got {count}")
    if count >= len(dataset.orders):
        return dataset
    orders = dataset.orders[:count]
    order_codes = {order.code for order in orders}
    lines = tuple(line for line in dataset.order_lines if line.order_code in order_codes)
    batch_codes = {line.roast_batch_code for line in lines}
    return dataclasses.replace(
        dataset,
        orders=orders,
        order_lines=lines,
        roast_batches=tuple(b for b in dataset.roast_batches if b.code in batch_codes),
        roast_batch_lots=tuple(
            c for c in dataset.roast_batch_lots if c.roast_batch_code in batch_codes
        ),
    )
