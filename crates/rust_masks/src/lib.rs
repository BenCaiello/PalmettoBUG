// Written with AI assistance, but also intentionally made in a more "manual", smaller-pieces-at-a-time manner for the sake of learning rust better
use imageproc::region_labelling::{connected_components, Connectivity};
use image::{GrayImage, Luma};
use std::collections::HashMap;

fn find_unique2(mask: &Vec<Vec<usize>>, max_label: usize) -> Vec<usize> {
    let mut seen = vec![false; max_label + 1];
    for &px in mask.iter().flatten() {
        seen[px] = true;
    }
    return seen.iter()
        .enumerate()
        .filter_map(|(i, &flag)| flag.then_some(i))
        .collect()

}

pub fn mask_boolean (
    mask1: &Vec<Vec<usize>>,
    mask2: &Vec<Vec<usize>>,
    kind: &str,
    object_threshold: usize,
    pixel_threshold: usize,
    re_order: bool
) -> Vec<Vec<usize>> {
    
    let mut output: Vec<Vec<usize>> = mask1.clone();
    let mask1_flat: Vec<usize> = mask1.iter().flatten().copied().collect();
    let mask2_flat: Vec<usize> = mask2.iter().flatten().copied().collect();

    let maximum_mask1: usize = *mask1.iter().flatten().max().unwrap_or(&0);
    let maximum_mask2: usize = *mask2.iter().flatten().max().unwrap_or(&0);

    let mask1_values: Vec<usize> = find_unique2(&mask1, maximum_mask1);
    let mask2_values: Vec<usize> = find_unique2(&mask2, maximum_mask2);
    let length_mask1_values: usize = mask1_values.len();
    let length_mask2_values: usize = mask2_values.len();

    

    if (maximum_mask1 != length_mask1_values - 1) || (maximum_mask2 != length_mask2_values - 1){
        if maximum_mask1.saturating_mul(maximum_mask2) < 1_000_000_000{
            println!("Warning! Non dense labels passed to rust mask_boolean function. Proceeding as N(masks in mask1) * N(masks in mask2) is less than 1 billion.")
        }else{
            panic!("Input Error: Dense label assumption failed and N(masks in mask1) * N(masks in mask2) is greater than 1 billion. This risks extreme memory usage in rust mask_boolean function");
        }
    }

    // Loops to find overlapping pixels, then overlapping objects
    let mut px_overlap_array: Vec<Vec<usize>> = vec![vec![0;maximum_mask2 + 1];maximum_mask1 + 1]; // Instatiate an array 
    for (m1,m2) in mask1_flat.iter().zip(mask2_flat.iter()){ // iterate through every pixel
        if (*m1 != 0) && (*m2 != 0){
            px_overlap_array[*m1][*m2] += 1;                     // count overlaps for every mask1 value (will need to ignore 0's later)
        }
    }

    let mut obj_overlap_array: Vec<usize> = vec![0;maximum_mask1 + 1];   // This array serves a dual purpose: first we track object overlaps & check the object threshold, 
                                                                    // then we store the value to replace pixels in mask1 with:
                                                                    // either the array index if passing the threshold test (restoring the value with itself), 
                                                                    // or 0 if failing the threshold, thereby eliminating the failed mask from the output
    let mut obj_overlap_array_2: Vec<usize> = vec![0;maximum_mask2 + 1];

    for &m1 in mask1_values.iter(){                      // now iterate over every unique value combination to see if they pass the pixel threshold
        for &m2 in mask2_values.iter(){  
            if px_overlap_array[m1][m2] >= pixel_threshold{
                obj_overlap_array[m1] += 1;                        // count every time a mask2 object counts as "overlapping" with a particular mask1 object by passing the threshold
                if (kind == "difference2") || (kind == "intersection2"){
                    obj_overlap_array_2[m2] += 1;                  // Can simultaneously collect inverse object array as well
                }
            }
        }
    }


    for (ii,i) in obj_overlap_array.iter_mut().enumerate(){     // iterate over object overlap counts, handling appropriately depending on intersection or difference
        if (kind == "intersection1") || (kind == "intersection2") {
            if *i < object_threshold{       // if under object threshold, set output value to 0 (to be dropped from output)
                *i = 0;
            } else {*i = ii;}               // if failing threshold, set the output value to the original mask value (encoded by the vector position)
        }
        if (kind == "difference1") || (kind == "difference2") {
            if *i >= object_threshold{       // if greater than object threshold, set output value to 0 (to be dropped from output)
                *i = 0;
            } else {*i = ii;}               // if failing threshold, set the output value to the original mask value (encoded by the vector position)
        }
    }

    // set every pixel in the output to the value from obj_overlap_array -- zero if failing the overlap threshold, the original mask1 value if passing the threshold
    for row in output.iter_mut(){
        for px in row{
            *px = obj_overlap_array[*px];  // replace the pixel with the value from the object_overlap_array (which now holds the pass/fail values for each mask)
        }
    }


    if (kind == "difference2") || kind == ("intersection2"){
        for (ii,i) in obj_overlap_array_2.iter_mut().enumerate(){     // iterate over object overlap counts, handling appropriately depending on intersection or difference
            if kind == "intersection2" {
                if *i < object_threshold{       // if under object threshold, set output value to 0 (to be dropped from output)
                    *i = 0;
                } else {*i = ii;}               // if failing threshold, set the output value to the original mask value (encoded by the vector position)
            }
            if kind == "difference2" {
                if *i >= object_threshold{       // if greater than object threshold, set output value to 0 (to be dropped from output)
                    *i = 0;
                } else {*i = ii;}               // if failing threshold, set the output value to the original mask value (encoded by the vector position)
            }  
        }   

        // set every pixel in the output to the value from obj_overlap_array_2 -- zero if failing the overlap threshold, the original mask1 value if passing the threshold
        for (row, r2) in output.iter_mut().zip(mask2.iter()){
            for (px, p2) in row.iter_mut().zip(r2.iter()){
                if *px == 0 {      // Don't overwrite any non-zero pixels in output
                    let replacement = obj_overlap_array_2[*p2];
                    if replacement != 0 {
                        *px = replacement + maximum_mask1;       // replace the pixel with the value from the object_overlap_array (which now holds the pass/fail values for each mask)
                    }
                }
            }
        }
    }

    if re_order {
        // Find output's maximum label
        let max_label = *output.iter().flatten().max().unwrap_or(&0);

        // Boolean array to track which labels exist
        let mut seen = vec![false; max_label + 1];
        for &px in output.iter().flatten() {
            seen[px] = true;
        }

        // Build LUT: old label -> new label
        let increment: usize =
            if seen[0] { 0 } else { 1 };

        let mut lut = vec![0usize; max_label + 1];
        let mut new_id = increment;

        for (label, &exists) in seen.iter().enumerate() {
            if exists {
                lut[label] = new_id;
                new_id += 1;
            }
        }

        // Rewrite pixels using LUT
        for px in output.iter_mut().flatten() {
            *px = lut[*px];
        }
    }


    return output
}

pub fn smooth_isolated_pixels(
    class_map: Vec<Vec<usize>>,
    class_num: usize,
    threshold: usize,
    search_radius: usize,
    mode_mode: &str,
    fill_in: bool,
    warn: bool,
) -> Vec<Vec<usize>> {

    let height = class_map.len();
    let width = class_map[0].len();

    // Track original background (Python zero_number logic)
    let background: Vec<Vec<bool>> = (0..height)
        .map(|i| (0..width).map(|j| class_map[i][j] == 0).collect())
        .collect();

    let mut kept = vec![vec![0usize; width]; height];

    // Phase 1: remove small objects per class
    for class_id in 1..=class_num {
        let mask: Vec<Vec<bool>> = (0..height)
            .map(|i| (0..width).map(|j| class_map[i][j] == class_id).collect())
            .collect();

        let filtered =
            remove_small_objects_binary(&mask, threshold, search_radius + 1);

        for i in 0..height {
            for j in 0..width {
                if filtered[i][j] && (kept[i][j] == 0)  {
                    kept[i][j] = class_map[i][j];
                }
            }
        }
    }

    // Phase 2: fill-in via mode
    if fill_in {
        
        for i in 0..height {
            for j in 0..width {
                // DO NOT fill original background pixels
                if kept[i][j] == 0 && !background[i][j] {
                    let reference = match mode_mode {
                        "original_image" => &class_map,
                        "dropped_image" => &kept,
                        _ => panic!("mode_mode must be 'original_image' or 'dropped_image'"),
                    };
                    let mode = find_mode(
                        reference,
                        &[i, j],
                        search_radius,
                        warn,
                    );
                    if mode != 0 { kept[i][j] = mode; }
                }
            }
        }
    }

    kept
}


fn find_mode(
    array: &[Vec<usize>],
    point: &[usize],
    mut radius: usize,
    warn: bool,
) -> usize {
    let height = array.len();
    let width = array[0].len();

    let x = point[0]; // row
    let y = point[1]; // column

    let max_radius = height.max(width);

    loop {
        if radius > max_radius {
            return 0;
        }

        let x_min = x.saturating_sub(radius);
        let x_max = (x + radius).min(height - 1);
        let y_min = y.saturating_sub(radius);
        let y_max = (y + radius).min(width - 1);

        let mut counts: HashMap<usize, usize> = HashMap::new();  
        for i in x_min..=x_max {
            for j in y_min..=y_max {
                let v = array[i][j];
                if v != 0 {
                    *counts.entry(v).or_insert(0) += 1;
                }
            }
        }

        if let Some((&mode, _)) = counts.iter().max_by_key(|(_, c)| *c) {
            return mode;
        }

        if warn {
            println!(
                "No nonzero values around ({},{}) — expanding search radius",
                x, y
            );
        }

        radius += 1;
    }
}

/// Remove connected components smaller than `min_size`
/// Connectivity must match skimage semantics
// Written by AI, consciously meant to emulate the behaviour of skimage's remove small objects function
fn remove_small_objects_binary(
    mask: &Vec<Vec<bool>>,
    min_size: usize,
    connectivity: usize,
) -> Vec<Vec<bool>> {

    let height = mask.len();
    let width = mask[0].len();

    let mut img = GrayImage::new(width as u32, height as u32);
    for y in 0..height {
        for x in 0..width {
            img.put_pixel(
                x as u32,
                y as u32,
                Luma([if mask[y][x] { 255 } else { 0 }]),
            );
        }
    }

    let conn = match connectivity {
        1 => Connectivity::Four,
        _ => Connectivity::Eight,
    };

    let labels = connected_components(&img, conn, Luma(0));

    let mut counts: HashMap<u32, usize> = HashMap::new();
    for p in labels.pixels() {
        let label = p.0[0];
        if label != 0 {
            *counts.entry(label).or_insert(0) += 1;
        }
    }

    let mut output = vec![vec![false; width]; height];
    for y in 0..height {
        for x in 0..width {
            let label = labels.get_pixel(x as u32, y as u32).0[0];
            if label != 0 && counts.get(&label).copied().unwrap_or(0) >= min_size {
                output[y][x] = true;
            }
        }
    }

    output
}