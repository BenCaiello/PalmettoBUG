// Written with AI assistance, but also intentionally made in a more "manual", smaller-pieces-at-a-time manner for the sake of learning rust better


fn find_unique1(mask: &Vec<usize>) -> Vec<usize> {
    let mut mask_values: Vec<usize> = mask.iter().copied().collect();
    mask_values.sort_unstable();
    mask_values.dedup();
    return mask_values
}

fn find_unique2(mask: &Vec<Vec<usize>>) -> Vec<usize> {
    let mut mask_values: Vec<usize> = mask.iter().flatten().copied().collect();
    mask_values.sort_unstable();
    mask_values.dedup();
    return mask_values
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
    let mask1_values: Vec<usize> = find_unique2(&mask1);
    let maximum_mask1: usize = *mask1.iter().flatten().max().unwrap_or(&0);

    for j in mask1_values.iter(){
        if *j == 0 {continue} else { //skip 0, it is not a mask!
            let matches: Vec<usize> = mask1.iter().flatten().zip(mask2.iter().flatten()).filter_map(|(&m, &v)| (m == *j).then_some(v)).collect();

            let unique_matches: Vec<usize> = find_unique1(&matches);
            let mut object_counter: usize = 0;

            for k in unique_matches.iter(){ 
                if matches.iter().filter(|&x| x == k).count() > pixel_threshold{
                    object_counter += 1;
                }
            }

            if kind == "intersection1" || kind == "intersection2" {
                if object_counter < object_threshold{
                    for row in output.iter_mut(){
                        for px in row{
                            if *px == *j {*px = 0}
                        }
                    }
                }
            }
            if kind == "difference1" || kind == "difference2"{
                if object_counter > object_threshold{
                    for row in output.iter_mut(){
                        for px in row{
                            if *px == *j {*px = 0}
                        }
                    }
                }
            }
        }
    }

    if kind == "difference2" || kind == "intersection2"{
        let mask2_values: Vec<usize> = find_unique2(&mask2);
        for j in mask2_values.iter(){
            if *j == 0 {continue} else {
                let matches: Vec<usize> = mask2.iter().flatten().zip(mask1.iter().flatten()).filter_map(|(&m, &v)| (m == *j).then_some(v)).collect();
                let unique_matches: Vec<usize> = find_unique1(&matches);
                let mut object_counter: usize = 0;
                for k in unique_matches.iter(){ 
                    if matches.iter().filter(|&&x| x == *k).count() > pixel_threshold{
                        object_counter += 1;
                    }
                }

                if ((kind == "difference2") && (object_counter < object_threshold)) || ((kind == "intersection2") && (object_counter > object_threshold)) {                       
                    for (row1, row2) in output.iter_mut().zip(mask2.iter()) {
                            for (m1, &m2) in row1.iter_mut().zip(row2.iter()) {
                                if m2 == *j && *m1 == 0 {
                                    *m1 = *j + maximum_mask1;
                            }
                        }
                    }

                }
            }

        }

    }

    if re_order {
        let increment: usize = if output.iter().flatten().any(|&x| x == 0) { 0 } else { 1 };
        let mut unique_in_output: Vec<usize> = find_unique2(&output); 
        unique_in_output.sort();
        for (m,mm) in unique_in_output.iter().enumerate(){
            for row in output.iter_mut(){
                for px in row{
                    if *px == *mm{
                        *px = m + increment
                    }
                }
            }
        }
    }
    return output
}