# Which clips stand in for the smoke

Type: grilling
Status: resolved
Assignee: wayfinder session
Blocked by:

## Question

Which masked video is the cable-corner case, which is the clean floor, and how long is each clip?

Both `max_individuals` settings run on the same two clips. Outputs stay out of `H:\Open Field - superanimal\`.

## Comments

- 2026-10-30: Masked videos look clean of second mice. The 1.8× stills on this machine still show cable pixels inside the pose zone on Test 1 (lower left) and on the edge of it on Test 200 (lower right). Test 120's cables fall outside the zone. Waiting on a look at those two masked corners before locking the clips.

## Answer

No clips. Skip the two-slot comparison. Lock `max_individuals` at 1 for the full run.

The masked videos, as inspected on the other machine, show no second subject. The Test 1 still on this machine still has cable pixels inside the 1.8× zone. The full run keeps the single highest-scoring box on those frames anyway.
