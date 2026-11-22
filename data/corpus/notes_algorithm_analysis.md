---
source: notes_algorithm_analysis
title: "Course notes: Algorithm analysis"
course: "C++ data structures"
provenance: "Written for the Misconceptor project on 2026-11-22 in the voice of the course instructor. Original text, not copied from a textbook or the web. Course conventions follow the Mohler ASAG instructor answers; see data/corpus/README.md."
default_concepts: [algorithm_analysis]
---

# Algorithm analysis

## Counting operations
<!-- chunk: ana.counting-operations | concepts: algorithm_analysis, counting_operations, input_size -->

There are two ways to find out how long an algorithm takes. The experimental approach is to implement the algorithm and measure the physical running time. It gives real numbers, but they depend on the machine, the compiler, the inputs that were tried and whatever else the computer was doing, and it needs a finished program.

The analytic approach, which we use for the rest of the course, is to count the basic operations that the algorithm performs, as a function of the size of its input. The input size is written n or N: the length of the array, or the number of nodes in the list or tree. A basic operation is one that takes a fixed amount of time whatever n is: comparing two elements, copying one element, following one pointer, one arithmetic operation.

For sorting and searching we usually count the comparisons between elements, and sometimes also the moves (copies or swaps), because these dominate the running time. Everything else the algorithm does happens at most a fixed number of times per comparison.

Counting gives a formula in n, such as n - 1 or n(n - 1)/2. We then keep only how the formula grows as n becomes large, which is what Big-O notation records.

## Best case, average case and worst case
<!-- chunk: ana.cases | concepts: algorithm_analysis, best_case, worst_case, average_case, linear_search -->

For most algorithms the number of operations depends not only on how many elements there are but also on which elements they are and how they are arranged. A linear search for a value in an array of n elements may stop at the first element, or it may have to look at all n. So we describe an algorithm with three functions of n.

The worst case is the largest number of operations over all inputs of size n. It is a guarantee: the algorithm never does more work than this.

The best case is the smallest number of operations over all inputs of size n.

The average case is the expected number of operations over all inputs of size n, under an assumption about how likely each input is. The usual assumption is that every arrangement is equally likely.

For linear search in an array of n elements: the best case is 1 comparison (the value is in the first position), the worst case is n comparisons (the value is in the last position or is absent), and the average case is about n/2 comparisons when the value is present.

Each of the three is a statement about inputs of the same size n. Whenever you give a count, say which case it belongs to and which input produces it. Quoting the worst-case formula as the best case, or the reverse, is a common slip.

## Best case means best arrangement, not smallest input
<!-- chunk: ana.best-case-arrangement | concepts: algorithm_analysis, best_case, input_size, insertion_sort -->

All three cases are defined for the same input size n. The best case is the most favourable arrangement of n elements. It is not the smallest input.

Asking for the best case of a sorting algorithm does not mean asking what happens for an array of one or two elements. Every algorithm is fast on a tiny input, so that would say nothing about the algorithm. The size n stays general, and we ask which of the possible arrays of length n makes the algorithm do the least work.

For insertion sort the most favourable arrangement is an array that is already sorted: each element is compared with its left neighbour once and stays where it is, which gives N operations for an array of length N. For linear search it is an array in which the value being looked for happens to come first. For selection sort and merge sort the arrangement makes no difference to the order of growth, so their best case and worst case are of the same order.

A useful check: a best-case count is still an expression in n, such as n or n log n. A count of exactly 1 operation is a best case only for an algorithm that really can stop after one step on an arbitrarily large input, as linear search can. A sort cannot, because it has to look at every element at least once.

## Asymptotic notation
<!-- chunk: ana.big-o | concepts: algorithm_analysis, asymptotic_notation, big_o, growth_rate -->

Big-O notation describes how an operation count grows as n grows, ignoring constant factors and lower-order terms. We say that f(n) is O(g(n)) if, for all sufficiently large n, f(n) is at most a constant multiple of g(n). So 3n + 5 is O(n). The count n(n - 1)/2 equals n^2/2 - n/2 and is O(n^2): the n^2 term dominates as n grows, and the factor one half is dropped.

The growth rates we meet in this course, from the slowest growing to the fastest, are O(1) constant, O(log n) logarithmic, O(n) linear, O(n log n), O(n^2) quadratic and O(2^n) exponential. For n equal to one million, log n is about 20, n log n is about twenty million, and n^2 is a million million.

Logarithms in this course are to base 2 unless we say otherwise: log n is the number of times n can be halved before it reaches 1. Logarithms to different bases differ only by a constant factor, so the base does not matter inside a Big-O.

Big-O is an upper bound on growth, and it can be applied to any of the three cases. It is correct to say that the worst case of insertion sort is O(n^2) and that its best case is O(n). Big-O does not by itself mean worst case, although a bound given without naming the case is normally read as the worst case.

## The cost of insertion sort
<!-- chunk: ana.insertion-sort | concepts: algorithm_analysis, sorting, insertion_sort, best_case, worst_case -->

Insertion sort takes one array element at a time, from left to right, and inserts it in the right position among the already sorted elements on its left. To insert an element it compares the element with its left neighbours one at a time, shifting each larger neighbour one position to the right, until it meets a neighbour that is not larger or reaches the start of the array.

Best case. The number of operations for insertion sort under a best-case scenario is N, the length of the array, and the best-case scenario is an array that is already sorted. Each element then needs a single comparison with its left neighbour and no shifting. Strictly that is N - 1 comparisons, because the first element has no left neighbour. In this course we state the count as N operations, which is O(n).

Worst case. The array is in reverse order. The element at position i is compared with, and shifted past, all i elements on its left, for a total of 1 + 2 + ... + (N - 1) = N(N - 1)/2 comparisons, which is O(n^2).

Average case. In a random arrangement each element travels about halfway back, which gives about N^2/4 comparisons, also O(n^2).

So N belongs to the best case and N(N - 1)/2 belongs to the worst case. Of the sorting algorithms in this course, insertion sort is the one whose cost depends most on how the input is arranged.

## The cost of selection sort
<!-- chunk: ana.selection-sort | concepts: algorithm_analysis, sorting, selection_sort, best_case, worst_case -->

Selection sort takes one array element at a time, from left to right, identifies the minimum from the remaining elements and swaps it with the current element. Put another way, it selects the minimum from the array and places it in the first position, then selects the minimum from the rest of the array and places it in the second position, and so forth.

Finding the minimum of the remaining elements means looking at every one of them. There is no way to stop early. The first pass makes N - 1 comparisons, the second N - 2, and so on down to 1, for a total of N(N - 1)/2 comparisons, which is O(n^2).

This count does not depend on the arrangement of the input. A sorted array, a reversed array and a random array of length N all cost exactly N(N - 1)/2 comparisons, so the best case, the average case and the worst case of selection sort are all O(n^2). Only the number of swaps varies, and it is never more than N - 1, one per pass. That is why selection sort is sometimes chosen when moving an element is expensive.

Compare this with insertion sort, which needs only N operations on a sorted array. Being sorted already helps insertion sort and does not help selection sort.

## The cost of merge sort
<!-- chunk: ana.merge-sort-cost | concepts: algorithm_analysis, sorting, merge_sort, divide_and_conquer -->

Merge sort splits the array into two halves, sorts each half recursively, and merges the two sorted halves. Its cost follows from the shape of the recursion.

Each level of the recursion handles all n elements once. At the top level one merge combines two halves of n/2 elements. At the next level two merges combine four quarters, and so on. Merging sorted pieces that hold n elements in total takes at most n - 1 comparisons, so every level costs about n operations.

The number of levels is the number of times n can be halved before the pieces reach base-case size, which is log n. The total is about n operations per level times log n levels: merge sort is O(n log n).

Unlike insertion sort, merge sort does this much work whatever the arrangement of the input, because it always splits in the middle and always merges at every level. Its best case, average case and worst case are all O(n log n). The exact number of comparisons in a merge varies a little with the data, but the order of growth does not.

The price is memory. Merging needs a temporary array of n elements, whereas insertion sort and selection sort sort the array in place. For large arrays merge sort is still far faster: for a million elements, n log n is about twenty million operations and n^2 is a million million.

## Searching a binary search tree: the cost is the height
<!-- chunk: ana.bst-search-height | concepts: algorithm_analysis, bst, search, tree_height, trees -->

A binary search tree is a binary tree in which, for any node, the left child is smaller than the parent, which in turn is smaller than the right child. The same holds for everything in the node's left and right subtrees.

To search for a key, start at the root and compare the key with the value in the node. If they are equal, the search is finished. If the key is smaller, continue in the left subtree; if it is larger, in the right subtree. An empty subtree means the key is not in the tree.

Each comparison moves the search one level down, and the other subtree is never looked at. The search therefore follows a single path from the root towards a leaf, and cannot examine more nodes than the longest such path contains. The height of a tree is the length of the longest path from the root to any of its leaves.

In this course the answer to how many comparisons, or how many steps, it takes to find an element in a binary search tree is the height of the tree. It can also be given as the log of the number of elements in the tree, which is the height when the tree is balanced. Counting the root, a search can examine one node more than the height. We ignore that difference: the cost grows with the height of the tree, not with the number of nodes.

## Balanced and degenerate trees
<!-- chunk: ana.balanced-vs-degenerate | concepts: algorithm_analysis, bst, tree_height, balanced_tree, degenerate_tree, worst_case -->

How large the height is depends on the shape of the tree, and the shape depends on the order in which the keys were inserted.

A balanced tree is as short as it can be: every level is full, except possibly the last. Level k of a binary tree holds up to 2^k nodes, so a tree with n nodes needs only about log n levels. The height of a balanced tree with n nodes is about log n. A balanced tree with 1,000 nodes has height 9, and one with a million nodes has height 19. Searching a balanced binary search tree is O(log n).

A degenerate tree is as tall as it can be: every node has only one child, so the tree is a chain. This is what a binary search tree turns into when the keys are inserted in sorted order. Its height is n - 1, and a search may have to pass through every node, exactly as in a linked list. Searching a degenerate binary search tree is O(n).

The complete statement is therefore this. Searching a binary search tree takes a number of steps equal to the height of the tree, which is about log n for the best shape, a balanced tree, and n - 1 for the worst shape, a degenerate tree. When we quote log n for a binary search tree we are assuming that the tree is balanced. A cost of n belongs only to the degenerate tree.

## Linear scan versus tree search
<!-- chunk: ana.linear-vs-tree-search | concepts: algorithm_analysis, search, linear_search, binary_search, bst, sorting -->

It helps to put the searches we know side by side, for a collection of n elements.

Linear scan of an unsorted array or of a linked list. Each comparison eliminates one element. The worst case is n comparisons, and the average is about n/2 when the element is present. O(n).

Binary search of a sorted array. Each comparison eliminates half of the remaining elements. At most about log n comparisons. O(log n).

Search in a balanced binary search tree. Each comparison eliminates one whole subtree, about half of the remaining nodes. At most about log n comparisons, the height of the tree. O(log n).

Counts such as n, n - 1 or n/2 are linear-scan counts. They describe looking at all of the elements, or at half of them. A search in a binary search tree does not visit every node, or half of the nodes, because every comparison discards a subtree without looking inside it. Visiting every node is what a traversal does (inorder, preorder or postorder), and a traversal is O(n).

Nor is n log n the cost of a search. O(n log n) is the cost of sorting n elements with merge sort, or of building a balanced tree by n insertions that cost O(log n) each. One search is a single path from the root towards a leaf: the height of the tree, which is O(log n) when the tree is balanced.
